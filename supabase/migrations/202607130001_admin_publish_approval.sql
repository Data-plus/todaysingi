-- 관리자 Instagram 릴스 게시 승인과 단일 실행 보장.

create unique index if not exists jobs_one_active_publish_reel_per_product
  on public.jobs (product_id)
  where type = 'publish_reel' and status in ('queued', 'claimed', 'running');

alter table public.jobs
  drop constraint if exists publish_reel_requires_approval;

alter table public.jobs
  add constraint publish_reel_requires_approval check (
    type <> 'publish_reel'
    or (
      approved_at is not null
      and approved_by is not null
      and max_attempts = 1
    )
  );

create or replace function public.approve_publish_reel(p_product_id bigint)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  existing_job_id uuid;
  created_job_id uuid;
  product_stage text;
  product_reel_url text;
begin
  if auth.uid() is null or not public.is_todaysingi_admin() then
    raise exception 'Instagram 게시 승인 권한이 없습니다'
      using errcode = '42501';
  end if;

  select stage, reel_url
    into product_stage, product_reel_url
  from public.products
  where id = p_product_id;

  if not found then
    raise exception '상품을 찾을 수 없습니다'
      using errcode = 'P0002';
  end if;

  if product_stage <> 'caption_ready' or product_reel_url is not null then
    raise exception '캡션이 완성되고 아직 게시되지 않은 상품만 승인할 수 있습니다'
      using errcode = '22023';
  end if;

  select id
    into existing_job_id
  from public.jobs
  where product_id = p_product_id
    and type = 'publish_reel'
    and status in ('queued', 'claimed', 'running')
  order by created_at desc
  limit 1;

  if existing_job_id is not null then
    return existing_job_id;
  end if;

  begin
    insert into public.jobs (
      product_id,
      type,
      payload,
      idempotency_key,
      priority,
      max_attempts,
      approved_at,
      approved_by
    ) values (
      p_product_id,
      'publish_reel',
      jsonb_build_object('requested_from', 'admin'),
      'publish_reel:' || p_product_id::text || ':' || gen_random_uuid()::text,
      30,
      1,
      now(),
      auth.uid()
    )
    returning id into created_job_id;
  exception
    when unique_violation then
      select id
        into existing_job_id
      from public.jobs
      where product_id = p_product_id
        and type = 'publish_reel'
        and status in ('queued', 'claimed', 'running')
      order by created_at desc
      limit 1;

      if existing_job_id is null then
        raise;
      end if;
      return existing_job_id;
  end;

  insert into public.activity_logs (
    product_id,
    job_id,
    actor,
    action,
    detail
  ) values (
    p_product_id,
    created_job_id,
    'admin',
    'publish_reel_approved',
    jsonb_build_object(
      'approved_by', auth.uid(),
      'requested_from', 'admin'
    )
  );

  return created_job_id;
end;
$$;

revoke all on function public.approve_publish_reel(bigint) from public, anon;
grant execute on function public.approve_publish_reel(bigint) to authenticated;
