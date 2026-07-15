from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "supabase" / "migrations" / "202607140001_cover_apply_publish_guard.sql"
CONTROL_DESK = ROOT / "admin" / "src" / "lib" / "controlDesk.ts"


def sql_source():
    return MIGRATION.read_text(encoding="utf-8").lower()


def sql_function(name: str) -> str:
    match = re.search(
        rf"create or replace function public\.{name}\([^)]*\).*?as \$\$(.*?)\$\$;",
        sql_source(),
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def typescript_function(name: str, next_name: str) -> str:
    source = CONTROL_DESK.read_text(encoding="utf-8")
    return source.split(f"export async function {name}", 1)[1].split(
        f"export async function {next_name}", 1
    )[0]


def test_publish_rpc_rejects_active_cover_jobs():
    sql = sql_source()
    assert "create or replace function public.approve_publish_reel" in sql
    assert "type = 'generate_cover'" in sql
    for status in ("queued", "claimed", "running"):
        assert f"'{status}'" in sql
    assert "errcode = '55000'" in sql
    assert "커버 적용 작업이 완료된 후 게시할 수 있습니다" in sql


def test_publish_rpc_keeps_admin_and_readiness_guards():
    sql = sql_source()
    assert "public.is_todaysingi_admin()" in sql
    assert "product_stage <> 'caption_ready'" in sql
    assert "product_reel_url is not null" in sql
    assert "grant execute on function public.approve_publish_reel(bigint) to authenticated" in sql


def test_cover_and_publish_rpcs_share_product_lock_before_state_reads():
    lock = "perform pg_advisory_xact_lock(p_product_id);"
    publish_rpc = sql_function("approve_publish_reel")
    cover_rpc = sql_function("enqueue_generate_cover")

    assert lock in publish_rpc
    assert lock in cover_rpc
    assert publish_rpc.index(lock) < publish_rpc.index("from public.products")
    assert publish_rpc.index(lock) < publish_rpc.index("type = 'generate_cover'")
    assert cover_rpc.index(lock) < cover_rpc.index("type = 'publish_reel'")


def test_cover_enqueue_rpc_is_admin_only_and_rejects_active_publish_jobs():
    sql = sql_source()
    cover_rpc = sql_function("enqueue_generate_cover")

    assert "security definer" in sql.split(
        "create or replace function public.enqueue_generate_cover", 1
    )[1]
    assert "public.is_todaysingi_admin()" in cover_rpc
    assert "insert into public.jobs" in cover_rpc
    assert "'generate_cover'" in cover_rpc
    assert "gen_random_uuid()" in cover_rpc
    assert "type = 'publish_reel'" in cover_rpc
    for status in ("queued", "claimed", "running"):
        assert f"'{status}'" in cover_rpc
    assert "revoke all on function public.enqueue_generate_cover(bigint, jsonb) from public, anon" in sql
    assert "grant execute on function public.enqueue_generate_cover(bigint, jsonb) to authenticated" in sql


def test_admin_cover_enqueue_and_retry_use_rpc_instead_of_direct_job_insert():
    enqueue = typescript_function("enqueueGenerateCover", "approvePublishReel")
    retry = typescript_function("retryJob", "createProduct")

    assert '.rpc("enqueue_generate_cover"' in enqueue
    assert "p_product_id: productId" in enqueue
    assert "p_payload: payload" in enqueue
    assert '.from("jobs").insert' not in enqueue
    assert "crypto.randomUUID" not in enqueue

    assert 'job.type === "generate_cover"' in retry
    assert '.rpc("enqueue_generate_cover"' in retry
    assert "p_product_id: job.productId" in retry
    assert "p_payload: job.payload" in retry
