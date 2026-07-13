-- Cloud Run Job은 서버 안전 작업만 선점하며 side effect 작업은 단일 시도만 허용한다.

create or replace function public.claim_next_cloud_job(
  p_worker_id text,
  p_lock_seconds integer default 900
)
returns setof public.jobs
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_lock_seconds < 60 or p_lock_seconds > 3600 then
    raise exception 'p_lock_seconds must be between 60 and 3600';
  end if;

  return query
  with candidate as (
    select j.id
    from public.jobs j
    where j.status = 'queued'
      and j.attempts < j.max_attempts
      and j.type in (
        'sync_ga4', 'cleanup_assets',
        'source_product', 'source_video', 'analyze_video',
        'generate_script', 'generate_voice', 'compose_video',
        'generate_cover', 'generate_caption', 'publish_reel', 'export_products'
      )
      and (j.type not in ('publish_reel', 'export_products') or j.max_attempts = 1)
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

revoke all on function public.claim_next_cloud_job(text, integer) from public, anon, authenticated;
grant execute on function public.claim_next_cloud_job(text, integer) to service_role;
