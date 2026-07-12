-- 통일형 릴스 커버 후보, 최종 커버와 Worker 작업 유형.

alter table public.jobs
  drop constraint if exists jobs_type_check;

alter table public.jobs
  add constraint jobs_type_check check (type in (
    'sync_pipeline', 'create_product', 'fetch_video', 'dub',
    'generate_cover', 'publish_reel', 'add_product'
  ));

alter table public.assets
  drop constraint if exists assets_kind_check;

alter table public.assets
  add constraint assets_kind_check check (kind in (
    'thumbnail', 'final_video', 'cover_candidate', 'reel_cover'
  ));

alter table public.assets
  add column if not exists metadata jsonb not null default '{}'::jsonb;

create index if not exists assets_product_kind_idx
  on public.assets (product_id, kind, created_at desc);
