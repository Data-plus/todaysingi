-- 한국 시간 오전 04:15에 GA4 Edge Function을 호출한다.
-- 실제 URL과 예약 호출 비밀은 Supabase Vault의 명명된 secret에서만 읽는다.

create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

select cron.unschedule(jobid)
from cron.job
where jobname = 'todaysingi-ga4-daily';

select cron.schedule(
  'todaysingi-ga4-daily',
  '15 19 * * *',
  $schedule$
  select net.http_post(
    url := (
      select decrypted_secret
      from vault.decrypted_secrets
      where name = 'ga4_project_url'
      limit 1
    ) || '/functions/v1/sync-ga4',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-ga4-cron-secret', (
        select decrypted_secret
        from vault.decrypted_secrets
        where name = 'ga4_cron_secret'
        limit 1
      )
    ),
    body := jsonb_build_object('days', 30)
  ) as request_id;
  $schedule$
);
