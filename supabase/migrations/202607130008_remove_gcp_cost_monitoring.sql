-- 중단한 GCP 비용/Cloud Run 실험 객체만 제거한다.

delete from public.jobs
where type = 'sync_gcp_costs';

delete from public.integration_syncs
where integration = 'gcp_billing';

drop function if exists public.request_gcp_cost_sync();
drop function if exists public.get_gcp_cost_overview(date);
drop function if exists public.replace_gcp_costs(
  date, date, jsonb, text, numeric, text
);

drop table if exists public.gcp_cost_daily;
drop table if exists public.gcp_cost_settings;

alter table public.integration_syncs
  drop constraint if exists integration_syncs_integration_check;
alter table public.integration_syncs
  add constraint integration_syncs_integration_check check (
    integration in ('ga4', 'coupang', 'meta')
  );

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
