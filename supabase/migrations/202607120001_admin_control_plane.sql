-- 오늘의신기템 온라인 관리자 control plane.
-- 실행 전 Supabase Auth에서 이메일 가입을 닫고 plusmg@gmail.com 계정만 생성한다.

create extension if not exists pgcrypto;

create or replace function public.is_todaysingi_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select lower(coalesce(auth.jwt() ->> 'email', '')) = 'plusmg@gmail.com';
$$;

revoke all on function public.is_todaysingi_admin() from public;
grant execute on function public.is_todaysingi_admin() to authenticated;

create table public.products (
  id bigint primary key,
  title text not null check (length(trim(title)) > 0),
  coupang_url text not null unique check (coupang_url like 'https://%'),
  ali_url text check (ali_url is null or ali_url like 'https://%'),
  partners_link text check (partners_link is null or partners_link like 'https://%'),
  reel_url text check (reel_url is null or reel_url like 'https://%'),
  ig_media_id text,
  site_product_id text,
  price integer check (price is null or price >= 0),
  image_url text,
  stage text not null default 'sourced' check (stage in (
    'sourced', 'video_ready', 'script_ready', 'audio_ready', 'caption_ready',
    'published', 'linked', 'ads_running', 'analyzed'
  )),
  note text not null default '',
  local_snapshot jsonb not null default '{}'::jsonb,
  synced_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.workers (
  id text primary key check (length(id) between 1 and 128),
  name text not null,
  status text not null default 'offline' check (status in ('online', 'busy', 'offline', 'error')),
  current_job_id uuid,
  version text,
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  product_id bigint references public.products(id) on delete cascade,
  type text not null check (type in (
    'sync_pipeline', 'fetch_video', 'dub', 'publish_reel', 'add_product'
  )),
  status text not null default 'queued' check (status in (
    'queued', 'claimed', 'running', 'succeeded', 'failed', 'cancelled'
  )),
  payload jsonb not null default '{}'::jsonb,
  result jsonb not null default '{}'::jsonb,
  idempotency_key text not null unique,
  priority smallint not null default 100 check (priority between 0 and 1000),
  progress smallint not null default 0 check (progress between 0 and 100),
  attempts smallint not null default 0 check (attempts between 0 and 20),
  max_attempts smallint not null default 3 check (max_attempts between 1 and 20),
  claimed_by text references public.workers(id) on delete set null,
  lock_expires_at timestamptz,
  error_summary text,
  approved_at timestamptz,
  approved_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  updated_at timestamptz not null default now()
);

alter table public.workers
  add constraint workers_current_job_fkey
  foreign key (current_job_id) references public.jobs(id) on delete set null;

create table public.job_logs (
  id bigint generated always as identity primary key,
  job_id uuid not null references public.jobs(id) on delete cascade,
  level text not null default 'info' check (level in ('debug', 'info', 'warning', 'error')),
  message text not null check (length(message) between 1 and 4000),
  created_at timestamptz not null default now()
);

create table public.assets (
  id uuid primary key default gen_random_uuid(),
  product_id bigint not null references public.products(id) on delete cascade,
  job_id uuid references public.jobs(id) on delete set null,
  kind text not null check (kind in ('thumbnail', 'final_video')),
  storage_path text not null unique,
  mime_type text not null,
  bytes bigint check (bytes is null or bytes >= 0),
  duration_seconds numeric check (duration_seconds is null or duration_seconds >= 0),
  checksum_sha256 text,
  review_status text not null default 'pending' check (review_status in ('pending', 'approved', 'changes_requested', 'rejected')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.activity_logs (
  id bigint generated always as identity primary key,
  product_id bigint references public.products(id) on delete set null,
  job_id uuid references public.jobs(id) on delete set null,
  actor text not null check (actor in ('admin', 'worker', 'system')),
  action text not null,
  detail jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index jobs_queue_idx on public.jobs (priority, created_at)
  where status = 'queued';
create index jobs_product_created_idx on public.jobs (product_id, created_at desc);
create index job_logs_job_created_idx on public.job_logs (job_id, created_at);
create index assets_product_created_idx on public.assets (product_id, created_at desc);
create index activity_logs_created_idx on public.activity_logs (created_at desc);
create index workers_last_seen_idx on public.workers (last_seen_at desc);

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger products_touch_updated_at before update on public.products
for each row execute function public.touch_updated_at();
create trigger workers_touch_updated_at before update on public.workers
for each row execute function public.touch_updated_at();
create trigger jobs_touch_updated_at before update on public.jobs
for each row execute function public.touch_updated_at();
create trigger assets_touch_updated_at before update on public.assets
for each row execute function public.touch_updated_at();

create or replace function public.claim_next_job(p_worker_id text, p_lock_seconds integer default 300)
returns setof public.jobs
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_lock_seconds < 30 or p_lock_seconds > 3600 then
    raise exception 'p_lock_seconds must be between 30 and 3600';
  end if;

  return query
  with candidate as (
    select j.id
    from public.jobs j
    where j.status = 'queued'
      and j.attempts < j.max_attempts
    order by j.priority asc, j.created_at asc
    for update skip locked
    limit 1
  )
  update public.jobs j
  set status = 'claimed',
      claimed_by = p_worker_id,
      lock_expires_at = now() + make_interval(secs => p_lock_seconds),
      attempts = j.attempts + 1,
      started_at = coalesce(j.started_at, now()),
      updated_at = now()
  from candidate c
  where j.id = c.id
  returning j.*;
end;
$$;

revoke all on function public.claim_next_job(text, integer) from public, anon, authenticated;
grant execute on function public.claim_next_job(text, integer) to service_role;

create or replace function public.requeue_expired_jobs()
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  affected integer;
begin
  update public.jobs
  set status = case when attempts < max_attempts then 'queued' else 'failed' end,
      claimed_by = null,
      lock_expires_at = null,
      error_summary = case when attempts < max_attempts then error_summary else coalesce(error_summary, 'Worker lock expired') end,
      updated_at = now()
  where status in ('claimed', 'running')
    and lock_expires_at < now();
  get diagnostics affected = row_count;
  return affected;
end;
$$;

revoke all on function public.requeue_expired_jobs() from public, anon, authenticated;
grant execute on function public.requeue_expired_jobs() to service_role;

alter table public.products enable row level security;
alter table public.workers enable row level security;
alter table public.jobs enable row level security;
alter table public.job_logs enable row level security;
alter table public.assets enable row level security;
alter table public.activity_logs enable row level security;

create policy admin_all_products on public.products for all to authenticated
using ((select public.is_todaysingi_admin())) with check ((select public.is_todaysingi_admin()));
create policy admin_read_workers on public.workers for select to authenticated
using ((select public.is_todaysingi_admin()));
create policy admin_all_jobs on public.jobs for all to authenticated
using ((select public.is_todaysingi_admin())) with check ((select public.is_todaysingi_admin()));
create policy admin_read_job_logs on public.job_logs for select to authenticated
using ((select public.is_todaysingi_admin()));
create policy admin_all_assets on public.assets for all to authenticated
using ((select public.is_todaysingi_admin())) with check ((select public.is_todaysingi_admin()));
create policy admin_read_activity on public.activity_logs for select to authenticated
using ((select public.is_todaysingi_admin()));

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('completed-assets', 'completed-assets', false, 262144000, array['video/mp4', 'image/jpeg', 'image/webp'])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create policy admin_read_completed_assets on storage.objects for select to authenticated
using (bucket_id = 'completed-assets' and (select public.is_todaysingi_admin()));
create policy admin_write_completed_assets on storage.objects for insert to authenticated
with check (bucket_id = 'completed-assets' and (select public.is_todaysingi_admin()));
