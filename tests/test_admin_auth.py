from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_login_uses_github_oauth_without_email_magic_link():
    login = source("admin/src/components/Login.tsx")

    assert "signInWithOAuth" in login
    assert 'provider: "github"' in login
    assert "adminRedirectUrl" in login
    assert "signInWithOtp" not in login
    assert "이메일로 로그인" not in login


def test_admin_session_requires_email_and_github_provider():
    app = source("admin/src/App.tsx")
    auth = source("admin/src/lib/auth.ts")

    assert "isAuthorizedAdminSession" in app
    assert "isAuthorizedAdminSession(session" in app
    assert "adminEmail" in auth
    assert 'providers.includes("github")' in auth


def test_redirect_url_has_a_safe_production_default():
    auth = source("admin/src/lib/auth.ts")

    assert "VITE_ADMIN_REDIRECT_URL" in auth
    assert "https://todaysingi.netlify.app/admin/" in auth


def test_github_auth_migration_uses_uuid_allow_list():
    sql = source(
        "supabase/migrations/202607120002_admin_github_auth.sql"
    ).lower()

    assert "create table public.admin_users" in sql
    assert "user_id uuid primary key references auth.users(id)" in sql
    assert "alter table public.admin_users enable row level security" in sql
    assert "revoke all on table public.admin_users from anon, authenticated" in sql
    assert "grant select, insert, update, delete on table public.admin_users to service_role" in sql
    assert "where au.user_id = (select auth.uid())" in sql
    assert "plusmg@gmail.com" not in sql


def test_authorize_admin_selects_exact_user_with_required_provider():
    from scripts.authorize_admin import select_admin_user

    users = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "email": "plusmg@gmail.com",
            "app_metadata": {"providers": ["email", "github"]},
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "email": "someone@example.com",
            "app_metadata": {"providers": ["github"]},
        },
    ]

    selected = select_admin_user(users, "PLUSMG@gmail.com", "github")

    assert selected["id"] == "11111111-1111-1111-1111-111111111111"


def test_authorize_admin_rejects_user_without_required_provider():
    from scripts.authorize_admin import AdminAuthorizationError, select_admin_user

    users = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "email": "plusmg@gmail.com",
            "app_metadata": {"providers": ["email"]},
        }
    ]

    with pytest.raises(AdminAuthorizationError, match="github"):
        select_admin_user(users, "plusmg@gmail.com", "github")
