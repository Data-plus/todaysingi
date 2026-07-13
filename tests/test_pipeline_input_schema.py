from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "202607130004_pipeline_inputs.sql"


def test_admin_can_only_upload_manual_pipeline_inputs_and_resume_waiting_job():
    assert MIGRATION.exists()
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create policy admin_upload_pipeline_inputs" in sql
    assert "bucket_id = 'pipeline-assets'" in sql
    assert "manual-inputs" in sql
    assert "create or replace function public.resume_pipeline_job" in sql
    assert "status <> 'waiting_input'" in sql
    assert "public.is_todaysingi_admin()" in sql
    assert "'product_price', 'product_image_url'" in sql
    assert "current_job.type <> 'source_product'" in sql
    assert "current_job.type <> 'source_video'" in sql
    assert "grant execute on function public.resume_pipeline_job(uuid, jsonb) to authenticated" in sql


def test_manual_video_registration_validates_job_product_and_storage_prefix():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create or replace function public.register_manual_video" in sql
    assert "source_video" in sql
    assert "manual-inputs/" in sql
    assert "kind" in sql and "'raw_video'" in sql
    assert "retention_class" in sql and "'review'" in sql
