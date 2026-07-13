-- Cloud Worker용 비공개 산출물과 명시적 보관·삭제 lifecycle.

alter table public.jobs
  drop constraint if exists jobs_type_check;

alter table public.jobs
  add constraint jobs_type_check check (type in (
    'sync_pipeline', 'sync_ga4', 'create_product',
    'source_product', 'source_video', 'fetch_video', 'analyze_video',
    'generate_script', 'generate_voice', 'dub', 'compose_video',
    'generate_cover', 'generate_caption', 'publish_reel',
    'add_product', 'export_products', 'cleanup_assets'
  ));

alter table public.jobs
  drop constraint if exists jobs_status_check;

alter table public.jobs
  add constraint jobs_status_check check (status in (
    'queued', 'claimed', 'running', 'waiting_input',
    'succeeded', 'failed', 'cancelled'
  ));

alter table public.assets
  drop constraint if exists assets_kind_check;

alter table public.assets
  add constraint assets_kind_check check (kind in (
    'thumbnail', 'raw_video', 'muted_video', 'frame', 'script', 'voice',
    'subtitle', 'final_video', 'cover_candidate', 'reel_cover', 'caption',
    'log', 'metrics'
  ));

alter table public.assets
  add column if not exists bucket_id text not null default 'completed-assets';
alter table public.assets
  add column if not exists retention_class text not null default 'review';
alter table public.assets
  add column if not exists expires_at timestamptz;
alter table public.assets
  add column if not exists cleanup_status text not null default 'active';
alter table public.assets
  add column if not exists deleted_at timestamptz;

alter table public.assets
  drop constraint if exists assets_bucket_check;
alter table public.assets
  drop constraint if exists assets_retention_class_check;
alter table public.assets
  drop constraint if exists assets_cleanup_status_check;
alter table public.assets
  drop constraint if exists assets_deleted_state_check;

alter table public.assets
  add constraint assets_bucket_check check (bucket_id in ('completed-assets', 'pipeline-assets'));
alter table public.assets
  add constraint assets_retention_class_check check (
    retention_class in ('ephemeral', 'review', 'keep')
  );
alter table public.assets
  add constraint assets_cleanup_status_check check (
    cleanup_status in ('active', 'cleanup_pending', 'deleted', 'failed')
  );
alter table public.assets
  add constraint assets_deleted_state_check check (
    (cleanup_status = 'deleted' and deleted_at is not null)
    or (cleanup_status <> 'deleted')
  );

update public.assets
set retention_class = case
  when kind in ('thumbnail', 'cover_candidate', 'reel_cover', 'script', 'subtitle', 'caption', 'log', 'metrics') then 'keep'
  when kind = 'final_video' then 'review'
  else retention_class
end;

create index if not exists assets_cleanup_due_idx
  on public.assets (expires_at, created_at)
  where cleanup_status in ('active', 'cleanup_pending', 'failed')
    and deleted_at is null
    and expires_at is not null;
create index if not exists assets_bucket_path_idx
  on public.assets (bucket_id, storage_path);

create unique index if not exists jobs_one_active_cleanup_assets
  on public.jobs ((type))
  where type = 'cleanup_assets' and status in ('queued', 'claimed', 'running');

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'pipeline-assets', 'pipeline-assets', false,
  524288000,
  array[
    'video/mp4', 'image/jpeg', 'image/png', 'image/webp',
    'audio/mpeg', 'audio/wav', 'audio/x-wav',
    'text/plain', 'application/json', 'application/x-subrip'
  ]
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists admin_read_pipeline_assets on storage.objects;
create policy admin_read_pipeline_assets on storage.objects for select to authenticated
using (bucket_id = 'pipeline-assets' and (select public.is_todaysingi_admin()));
