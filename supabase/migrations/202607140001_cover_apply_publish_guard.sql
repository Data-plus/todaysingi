-- 커버 적용이 끝나기 전에 Instagram 게시 승인이 앞서지 않도록 보장한다.

create or replace function public.approve_publish_reel(p_product_id bigint)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  existing_job_id uuid;
  active_cover_job_id uuid;
  created_job_id uuid;
  product_stage text;
  product_reel_url text;
begin
  if auth.uid() is null or not public.is_todaysingi_admin() then
    raise exception 'Instagram 게시 승인 권한이 없습니다'
      using errcode = '42501';
  end if;

  perform pg_advisory_xact_lock(p_product_id);

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
    into active_cover_job_id
  from public.jobs
  where product_id = p_product_id
    and type = 'generate_cover'
    and status in ('queued', 'claimed', 'running')
  order by created_at desc
  limit 1;

  if active_cover_job_id is not null then
    raise exception '커버 적용 작업이 완료된 후 게시할 수 있습니다'
      using errcode = '55000';
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

create or replace function public.enqueue_generate_cover(
  p_product_id bigint,
  p_payload jsonb
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  active_publish_job_id uuid;
  created_job_id uuid;
begin
  if auth.uid() is null or not public.is_todaysingi_admin() then
    raise exception '릴스 커버 생성 권한이 없습니다'
      using errcode = '42501';
  end if;

  perform pg_advisory_xact_lock(p_product_id);

  select id
    into active_publish_job_id
  from public.jobs
  where product_id = p_product_id
    and type = 'publish_reel'
    and status in ('queued', 'claimed', 'running')
  order by created_at desc
  limit 1;

  if active_publish_job_id is not null then
    raise exception '릴스 게시 작업이 진행 중인 동안 커버를 적용할 수 없습니다'
      using errcode = '55000';
  end if;

  insert into public.jobs (
    product_id,
    type,
    payload,
    idempotency_key,
    priority
  ) values (
    p_product_id,
    'generate_cover',
    coalesce(p_payload, '{}'::jsonb),
    'generate_cover:' || p_product_id::text || ':' || gen_random_uuid()::text,
    40
  )
  returning id into created_job_id;

  return created_job_id;
end;
$$;

revoke all on function public.enqueue_generate_cover(bigint, jsonb) from public, anon;
grant execute on function public.enqueue_generate_cover(bigint, jsonb) to authenticated;
