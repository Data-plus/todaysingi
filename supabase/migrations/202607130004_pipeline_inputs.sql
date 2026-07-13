-- 자동 수집이 막혔을 때 관리자만 Ali URL 또는 원본 영상을 제공한다.

drop policy if exists admin_upload_pipeline_inputs on storage.objects;
create policy admin_upload_pipeline_inputs on storage.objects for insert to authenticated
with check (
  bucket_id = 'pipeline-assets'
  and (storage.foldername(name))[1] = 'manual-inputs'
  and (select public.is_todaysingi_admin())
);

drop policy if exists admin_delete_pipeline_inputs on storage.objects;
create policy admin_delete_pipeline_inputs on storage.objects for delete to authenticated
using (
  bucket_id = 'pipeline-assets'
  and (storage.foldername(name))[1] = 'manual-inputs'
  and (select public.is_todaysingi_admin())
);

create or replace function public.resume_pipeline_job(p_job_id uuid, p_input jsonb)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  current_job public.jobs%rowtype;
  input_key text;
begin
  if auth.uid() is null or not public.is_todaysingi_admin() then
    raise exception '파이프라인 입력 권한이 없습니다'
      using errcode = '42501';
  end if;
  if jsonb_typeof(p_input) <> 'object' or p_input = '{}'::jsonb then
    raise exception '재개 입력은 비어 있지 않은 JSON 객체여야 합니다'
      using errcode = '22023';
  end if;
  for input_key in select jsonb_object_keys(p_input)
  loop
    if input_key not in (
      'ali_url', 'uploaded_asset_id', 'product_title',
      'product_description', 'product_price', 'product_image_url',
      'partners_link'
    ) then
      raise exception '허용되지 않는 파이프라인 입력입니다: %', input_key
        using errcode = '22023';
    end if;
  end loop;
  if p_input ? 'ali_url' and (p_input ->> 'ali_url') not like 'https://%' then
    raise exception 'Ali URL은 https:// 형식이어야 합니다'
      using errcode = '22023';
  end if;
  if p_input ? 'partners_link' and (p_input ->> 'partners_link') not like 'https://link.coupang.com/%' then
    raise exception '파트너스 링크 형식이 올바르지 않습니다'
      using errcode = '22023';
  end if;
  if p_input ? 'product_title' and nullif(btrim(p_input ->> 'product_title'), '') is null then
    raise exception '상품명은 비워 둘 수 없습니다'
      using errcode = '22023';
  end if;
  if p_input ? 'product_price' and (
    jsonb_typeof(p_input -> 'product_price') <> 'number'
    or (p_input ->> 'product_price') !~ '^[0-9]+$'
  ) then
    raise exception '상품 가격은 음수가 아닌 정수여야 합니다'
      using errcode = '22023';
  end if;
  if p_input ? 'product_image_url' and (p_input ->> 'product_image_url') not like 'https://%' then
    raise exception '상품 이미지 URL은 https:// 형식이어야 합니다'
      using errcode = '22023';
  end if;

  select * into current_job
  from public.jobs
  where id = p_job_id
  for update;
  if not found then
    raise exception '작업을 찾을 수 없습니다'
      using errcode = 'P0002';
  end if;
  if current_job.status <> 'waiting_input' then
    raise exception '입력 대기 중인 작업만 재개할 수 있습니다'
      using errcode = '22023';
  end if;
  if (p_input ?| array['product_title', 'product_description', 'product_price', 'product_image_url'])
     and current_job.type <> 'source_product' then
    raise exception '상품 정보는 상품 수집 작업에만 입력할 수 있습니다'
      using errcode = '22023';
  end if;
  if p_input ? 'ali_url' and current_job.type <> 'source_video' then
    raise exception 'Ali URL은 영상 수집 작업에만 입력할 수 있습니다'
      using errcode = '22023';
  end if;
  if p_input ? 'partners_link' and current_job.type <> 'export_products' then
    raise exception '파트너스 링크는 상품 내보내기 작업에만 입력할 수 있습니다'
      using errcode = '22023';
  end if;

  update public.jobs
  set status = 'queued',
      payload = payload || p_input,
      result = '{}'::jsonb,
      claimed_by = null,
      lock_expires_at = null,
      error_summary = null,
      max_attempts = least(20, greatest(max_attempts, attempts + 1)),
      updated_at = now()
  where id = p_job_id;

  if p_input ? 'ali_url' then
    update public.products set ali_url = p_input ->> 'ali_url'
    where id = current_job.product_id;
  end if;
  if p_input ? 'partners_link' then
    update public.products set partners_link = p_input ->> 'partners_link'
    where id = current_job.product_id;
  end if;
  if p_input ? 'product_title' then
    update public.products
    set title = btrim(p_input ->> 'product_title'),
        price = case when p_input ? 'product_price' then (p_input ->> 'product_price')::bigint else price end,
        image_url = case when p_input ? 'product_image_url' then p_input ->> 'product_image_url' else image_url end
    where id = current_job.product_id;
  end if;

  insert into public.activity_logs (product_id, job_id, actor, action, detail)
  values (current_job.product_id, p_job_id, 'admin', 'pipeline_input_submitted', jsonb_build_object('keys', p_input));
  return p_job_id;
end;
$$;

revoke all on function public.resume_pipeline_job(uuid, jsonb) from public, anon;
grant execute on function public.resume_pipeline_job(uuid, jsonb) to authenticated;

create or replace function public.register_manual_video(
  p_product_id bigint,
  p_job_id uuid,
  p_storage_path text,
  p_bytes bigint,
  p_mime_type text default 'video/mp4'
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  current_job public.jobs%rowtype;
  created_asset_id uuid;
begin
  if auth.uid() is null or not public.is_todaysingi_admin() then
    raise exception '원본 영상 등록 권한이 없습니다'
      using errcode = '42501';
  end if;
  if p_mime_type <> 'video/mp4' or p_bytes < 1 or p_bytes > 524288000 then
    raise exception 'MP4 영상은 오백 MB 이하만 등록할 수 있습니다'
      using errcode = '22023';
  end if;
  if p_storage_path not like ('manual-inputs/' || p_product_id::text || '/%')
     or p_storage_path like '%..%' then
    raise exception '수동 영상 Storage 경로가 올바르지 않습니다'
      using errcode = '22023';
  end if;

  select * into current_job
  from public.jobs
  where id = p_job_id
  for update;
  if not found then
    raise exception '작업을 찾을 수 없습니다'
      using errcode = 'P0002';
  end if;
  if current_job.product_id <> p_product_id
     or current_job.type <> 'source_video'
     or current_job.status <> 'waiting_input' then
    raise exception '해당 상품의 영상 입력 대기 작업이 아닙니다'
      using errcode = '22023';
  end if;

  insert into public.assets (
    product_id, job_id, kind, bucket_id, storage_path, mime_type, bytes,
    review_status, retention_class, cleanup_status, metadata
  ) values (
    p_product_id, p_job_id, 'raw_video', 'pipeline-assets', p_storage_path,
    p_mime_type, p_bytes, 'approved', 'review', 'active',
    jsonb_build_object('source', 'admin_upload')
  )
  on conflict (storage_path) do update set
    bytes = excluded.bytes,
    updated_at = now()
  returning id into created_asset_id;

  update public.jobs
  set status = 'queued',
      payload = payload || jsonb_build_object('uploaded_asset_id', created_asset_id),
      result = '{}'::jsonb,
      claimed_by = null,
      lock_expires_at = null,
      error_summary = null,
      max_attempts = least(20, greatest(max_attempts, attempts + 1)),
      updated_at = now()
  where id = p_job_id;

  insert into public.activity_logs (product_id, job_id, actor, action, detail)
  values (
    p_product_id, p_job_id, 'admin', 'manual_video_registered',
    jsonb_build_object('asset_id', created_asset_id, 'storage_path', p_storage_path)
  );
  return created_asset_id;
end;
$$;

revoke all on function public.register_manual_video(bigint, uuid, text, bigint, text) from public, anon;
grant execute on function public.register_manual_video(bigint, uuid, text, bigint, text) to authenticated;
