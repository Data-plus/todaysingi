"""Cloud Run에서 콘텐츠 작업 하나를 안전하게 완료하거나 입력 대기로 전환한다."""
from __future__ import annotations

from typing import Any

from .asset_cleanup import mark_failed_assets_for_expiry
from .control_plane import redact_text, utc_now
from .orchestrator import advance_after_success, mark_waiting_input
from .pipeline_handlers import PipelineInputRequired


def run_cloud_job(client, job: dict[str, Any], handlers) -> str:
    job_id = str(job.get("id") or "")
    product_id = job.get("product_id")
    try:
        client.update_job(job_id, status="running", progress=5, error_summary=None)
        client.log(job_id, f"Cloud 작업 시작: {job.get('type')}")
        result = handlers.handle(job)
        completed_at = utc_now().isoformat(timespec="seconds")
        client.update_job(
            job_id,
            status="succeeded",
            progress=100,
            result=result,
            lock_expires_at=None,
            finished_at=completed_at,
        )

        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        should_advance = payload.get("orchestrated") is True or job.get("type") == "publish_reel"
        if should_advance:
            product = client.get_product(product_id) if isinstance(product_id, int) else {}
            transition = advance_after_success(client, job, result, product=product or {})
            result = {**result, "transition": transition}
            client.update_job(job_id, result=result)
        client.log(job_id, "Cloud 작업 완료")
        return "succeeded"
    except PipelineInputRequired as exc:
        mark_waiting_input(
            client,
            job,
            input_kind=exc.input_kind,
            prompt=exc.prompt,
        )
        client.log(job_id, f"관리자 입력 대기: {exc.input_kind}", "warning")
        return "waiting_input"
    except Exception as exc:
        message = redact_text(str(exc)) or exc.__class__.__name__
        if isinstance(product_id, int):
            try:
                mark_failed_assets_for_expiry(
                    client,
                    client.list_product_assets(product_id),
                    job_status="failed",
                )
            except Exception as cleanup_exc:
                client.log(job_id, f"실패 asset 만료 설정 보류: {redact_text(str(cleanup_exc))}", "warning")
        client.update_job(
            job_id,
            status="failed",
            error_summary=message,
            lock_expires_at=None,
            finished_at=utc_now().isoformat(timespec="seconds"),
        )
        client.log(job_id, message, "error")
        return "failed"
