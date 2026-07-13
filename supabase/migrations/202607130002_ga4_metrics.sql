-- GA4 Data API 일별 집계. 동기화 실행은 Supabase Edge Function이 담당한다.

create table if not exists public.ga4_product_daily (
  metric_date date not null,
  item_id text not null check (length(trim(item_id)) between 1 and 128),
  product_id bigint references public.products(id) on delete set null,
  item_name text not null default '',
  clicks bigint not null default 0 check (clicks >= 0),
  synced_at timestamptz not null default now(),
  primary key (metric_date, item_id)
);

create table if not exists public.ga4_traffic_daily (
  metric_date date not null,
  source text not null check (length(trim(source)) between 1 and 256),
  medium text not null check (length(trim(medium)) between 1 and 128),
  sessions bigint not null default 0 check (sessions >= 0),
  active_users bigint not null default 0 check (active_users >= 0),
  synced_at timestamptz not null default now(),
  primary key (metric_date, source, medium)
);

create table if not exists public.integration_syncs (
  integration text primary key check (integration in ('ga4', 'coupang', 'meta')),
  status text not null default 'idle' check (
    status in ('idle', 'queued', 'running', 'succeeded', 'failed')
  ),
  last_attempt_at timestamptz,
  last_success_at timestamptz,
  range_start date,
  range_end date,
  row_count integer not null default 0 check (row_count >= 0),
  error_summary text,
  updated_at timestamptz not null default now(),
  check (range_start is null or range_end is null or range_start <= range_end)
);

create index if not exists ga4_product_daily_product_date_idx
  on public.ga4_product_daily (product_id, metric_date desc)
  where product_id is not null;
create index if not exists ga4_product_daily_date_idx
  on public.ga4_product_daily (metric_date desc);
create index if not exists ga4_traffic_daily_date_idx
  on public.ga4_traffic_daily (metric_date desc);

drop trigger if exists integration_syncs_touch_updated_at on public.integration_syncs;
create trigger integration_syncs_touch_updated_at before update on public.integration_syncs
for each row execute function public.touch_updated_at();

alter table public.ga4_product_daily enable row level security;
alter table public.ga4_traffic_daily enable row level security;
alter table public.integration_syncs enable row level security;

drop policy if exists admin_read_ga4_product_daily on public.ga4_product_daily;
create policy admin_read_ga4_product_daily
  on public.ga4_product_daily for select to authenticated
  using ((select public.is_todaysingi_admin()));
drop policy if exists admin_read_ga4_traffic_daily on public.ga4_traffic_daily;
create policy admin_read_ga4_traffic_daily
  on public.ga4_traffic_daily for select to authenticated
  using ((select public.is_todaysingi_admin()));
drop policy if exists admin_read_integration_syncs on public.integration_syncs;
create policy admin_read_integration_syncs
  on public.integration_syncs for select to authenticated
  using ((select public.is_todaysingi_admin()));

revoke all on table public.ga4_product_daily, public.ga4_traffic_daily,
  public.integration_syncs from anon;
revoke insert, update, delete on table public.ga4_product_daily,
  public.ga4_traffic_daily, public.integration_syncs from authenticated;
grant select on table public.ga4_product_daily, public.ga4_traffic_daily,
  public.integration_syncs to authenticated;
grant all on table public.ga4_product_daily, public.ga4_traffic_daily,
  public.integration_syncs to service_role;

insert into public.integration_syncs (integration, status)
values ('ga4', 'idle')
on conflict (integration) do nothing;

create or replace function public.replace_ga4_metrics(
  p_range_start date,
  p_range_end date,
  p_product_rows jsonb,
  p_traffic_rows jsonb
)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  affected integer;
begin
  if p_range_start is null or p_range_end is null
     or p_range_start > p_range_end
     or p_range_end - p_range_start > 89 then
    raise exception 'GA4 교체 기간이 올바르지 않습니다'
      using errcode = '22023';
  end if;

  if jsonb_typeof(p_product_rows) <> 'array'
     or jsonb_typeof(p_traffic_rows) <> 'array' then
    raise exception 'GA4 행은 JSON 배열이어야 합니다'
      using errcode = '22023';
  end if;

  delete from public.ga4_product_daily
  where metric_date between p_range_start and p_range_end;

  insert into public.ga4_product_daily (
    metric_date, item_id, product_id, item_name, clicks, synced_at
  )
  select
    row.metric_date,
    row.item_id,
    row.product_id,
    coalesce(row.item_name, ''),
    row.clicks,
    now()
  from jsonb_to_recordset(p_product_rows) as row(
    metric_date date,
    item_id text,
    product_id bigint,
    item_name text,
    clicks bigint
  )
  where row.metric_date between p_range_start and p_range_end;

  delete from public.ga4_traffic_daily
  where metric_date between p_range_start and p_range_end;

  insert into public.ga4_traffic_daily (
    metric_date, source, medium, sessions, active_users, synced_at
  )
  select
    row.metric_date,
    row.source,
    row.medium,
    row.sessions,
    row.active_users,
    now()
  from jsonb_to_recordset(p_traffic_rows) as row(
    metric_date date,
    source text,
    medium text,
    sessions bigint,
    active_users bigint
  )
  where row.metric_date between p_range_start and p_range_end;

  affected := jsonb_array_length(p_product_rows)
    + jsonb_array_length(p_traffic_rows);

  update public.integration_syncs
  set status = 'succeeded',
      last_attempt_at = coalesce(last_attempt_at, now()),
      last_success_at = now(),
      range_start = p_range_start,
      range_end = p_range_end,
      row_count = affected,
      error_summary = null
  where integration = 'ga4';

  return affected;
end;
$$;

revoke all on function public.replace_ga4_metrics(date, date, jsonb, jsonb)
  from public, anon, authenticated;
grant execute on function public.replace_ga4_metrics(date, date, jsonb, jsonb) to service_role;
