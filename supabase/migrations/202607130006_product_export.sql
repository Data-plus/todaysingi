-- 공개 링크 허브 export 대상 여부.

alter table public.products
  add column if not exists active boolean not null default true;

create index if not exists products_public_export_idx
  on public.products (stage, created_at, id)
  where active = true and partners_link is not null;
