"""DB 작업 성공을 다음 원격 파이프라인 단계 하나로 전이한다."""
from __future__ import annotations

from typing import Any, Mapping


TRANSITIONS: dict[str, tuple[str | None, str | None]] = {
    "source_product": (None, "source_video"),
    "source_video": ("video_ready", "analyze_video"),
    "analyze_video": (None, "generate_script"),
    "generate_script": ("script_ready", "generate_voice"),
    "generate_voice": ("audio_ready", "compose_video"),
    "compose_video": (None, "generate_cover"),
    "generate_cover": (None, "generate_caption"),
    "generate_caption": ("caption_ready", None),
    "export_products": ("linked", None),
}
WAITING_INPUT_KINDS = {
    "ali_url_or_video", "coupang_product", "llm_credentials",
    "typecast_credentials", "partners_link",
}


class OrchestratorError(ValueError):
    pass


def _product_id(job: Mapping[str, Any]) -> int:
    product_id = job.get("product_id")
    if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id < 1:
        raise OrchestratorError("원격 파이프라인 job에는 product_id가 필요합니다")
    return product_id


def next_transition(
    completed_type: str,
    product: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    if completed_type == "publish_reel":
        next_job = "export_products" if product.get("partners_link") else None
        return "published", next_job
    try:
        return TRANSITIONS[completed_type]
    except KeyError as exc:
        raise OrchestratorError(f"지원하지 않는 완료 단계입니다: {completed_type}") from exc


def start_pipeline(repository, product_id: int, *, coupang_url: str):
    if not isinstance(product_id, int) or product_id < 1:
        raise OrchestratorError("product_id는 일 이상의 정수여야 합니다")
    if not isinstance(coupang_url, str) or not coupang_url.startswith("https://"):
        raise OrchestratorError("쿠팡 URL은 https:// 형식이어야 합니다")
    return repository.enqueue_job_once(
        product_id,
        "source_product",
        {"coupang_url": coupang_url, "orchestrated": True},
        f"pipeline:{product_id}:source_product:v1",
        priority=20,
        max_attempts=3,
    )


def advance_after_success(
    repository,
    completed_job: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    product: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    job_id = str(completed_job.get("id") or "")
    job_type = str(completed_job.get("type") or "")
    if not job_id or not job_type:
        raise OrchestratorError("완료 job 식별자가 누락되었습니다")
    product_id = _product_id(completed_job)
    stage, next_job = next_transition(job_type, product or {})
    if stage:
        repository.update_product(product_id, stage=stage)

    waiting_for = None
    if job_type == "generate_caption":
        waiting_for = "admin_publish_approval"
    elif job_type == "publish_reel" and next_job is None:
        waiting_for = "partners_link"

    if next_job:
        repository.enqueue_job_once(
            product_id,
            next_job,
            {
                "upstream_job_id": job_id,
                "upstream_result": dict(result),
                "orchestrated": True,
            },
            f"pipeline:{product_id}:{next_job}:after:{job_id}",
            priority=50,
            max_attempts=1 if next_job == "export_products" else 3,
        )
    response: dict[str, Any] = {"stage": stage, "next_job": next_job}
    if waiting_for:
        response["waiting_for"] = waiting_for
    return response


def mark_waiting_input(
    repository,
    job: Mapping[str, Any],
    *,
    input_kind: str,
    prompt: str,
) -> dict[str, str]:
    job_id = str(job.get("id") or "")
    _product_id(job)
    if not job_id:
        raise OrchestratorError("waiting_input job ID가 없습니다")
    if input_kind not in WAITING_INPUT_KINDS:
        raise OrchestratorError("지원하지 않는 사용자 입력 종류입니다")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 500:
        raise OrchestratorError("사용자 입력 안내문이 올바르지 않습니다")
    result = {"waiting_for": input_kind, "prompt": prompt.strip()}
    repository.update_job(
        job_id,
        status="waiting_input",
        result=result,
        lock_expires_at=None,
    )
    return result
