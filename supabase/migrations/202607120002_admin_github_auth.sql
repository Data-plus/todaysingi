-- GitHub OAuth 관리자만 UUID 허용 목록으로 접근한다.

create table public.admin_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

comment on table public.admin_users is
  'service role만 변경할 수 있는 오늘의신기템 관리자 UUID 허용 목록';

alter table public.admin_users enable row level security;

revoke all on table public.admin_users from public;
revoke all on table public.admin_users from anon, authenticated;
grant select, insert, update, delete on table public.admin_users to service_role;

create or replace function public.is_todaysingi_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.admin_users au
    where au.user_id = (select auth.uid())
  );
$$;

revoke all on function public.is_todaysingi_admin() from public;
grant execute on function public.is_todaysingi_admin() to authenticated;
