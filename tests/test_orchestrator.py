from worker.orchestrator import (
    OrchestratorError,
    advance_after_success,
    mark_waiting_input,
    next_transition,
    start_pipeline,
)


class FakeRepository:
    def __init__(self):
        self.jobs = {}
        self.product_updates = []
        self.job_updates = []

    def enqueue_job_once(self, product_id, job_type, payload, idempotency_key, **options):
        if idempotency_key not in self.jobs:
            self.jobs[idempotency_key] = {
                "product_id": product_id,
                "type": job_type,
                "payload": payload,
                "options": options,
            }
        return self.jobs[idempotency_key]

    def update_product(self, product_id, **fields):
        self.product_updates.append((product_id, fields))

    def update_job(self, job_id, **fields):
        self.job_updates.append((job_id, fields))


def test_happy_path_stage_transitions_are_explicit():
    assert next_transition("source_product", {}) == (None, "source_video")
    assert next_transition("source_video", {}) == ("video_ready", "analyze_video")
    assert next_transition("analyze_video", {}) == (None, "generate_script")
    assert next_transition("generate_script", {}) == ("script_ready", "generate_voice")
    assert next_transition("generate_voice", {}) == ("audio_ready", "compose_video")
    assert next_transition("compose_video", {}) == (None, "generate_cover")
    assert next_transition("generate_cover", {}) == (None, "generate_caption")
    assert next_transition("generate_caption", {}) == ("caption_ready", None)


def test_success_enqueues_the_next_job_only_once_when_replayed():
    repository = FakeRepository()
    job = {"id": "job-source", "product_id": 4, "type": "source_video", "payload": {}}

    first = advance_after_success(repository, job, {"asset_id": "raw-1"})
    second = advance_after_success(repository, job, {"asset_id": "raw-1"})

    assert first["next_job"] == "analyze_video"
    assert second["next_job"] == "analyze_video"
    assert len(repository.jobs) == 1
    queued = next(iter(repository.jobs.values()))
    assert queued["payload"]["upstream_job_id"] == "job-source"
    assert repository.product_updates[-1] == (4, {"stage": "video_ready"})


def test_caption_ready_stops_for_admin_review():
    repository = FakeRepository()

    result = advance_after_success(
        repository,
        {"id": "job-caption", "product_id": 4, "type": "generate_caption", "payload": {}},
        {"caption_asset_id": "caption-1"},
    )

    assert result == {"stage": "caption_ready", "next_job": None, "waiting_for": "admin_publish_approval"}
    assert repository.jobs == {}


def test_publish_waits_for_partners_link_or_exports_when_present():
    assert next_transition("publish_reel", {"partners_link": None}) == ("published", None)
    assert next_transition("publish_reel", {"partners_link": "https://link.coupang.com/a/test"}) == ("published", "export_products")


def test_waiting_input_records_safe_prompt_without_enqueueing_next_step():
    repository = FakeRepository()

    result = mark_waiting_input(
        repository,
        {"id": "job-video", "product_id": 4, "type": "source_video"},
        input_kind="ali_url_or_video",
        prompt="AliExpress URL을 붙여 넣거나 원본 영상을 업로드하세요.",
    )

    assert result["waiting_for"] == "ali_url_or_video"
    assert repository.job_updates == [("job-video", {
        "status": "waiting_input",
        "result": {
            "waiting_for": "ali_url_or_video",
            "prompt": "AliExpress URL을 붙여 넣거나 원본 영상을 업로드하세요.",
        },
        "lock_expires_at": None,
    })]
    assert repository.jobs == {}


def test_new_pipeline_starts_with_product_source_once():
    repository = FakeRepository()
    start_pipeline(repository, 8, coupang_url="https://link.coupang.com/a/test")
    start_pipeline(repository, 8, coupang_url="https://link.coupang.com/a/test")
    assert len(repository.jobs) == 1
    assert next(iter(repository.jobs.values()))["type"] == "source_product"
