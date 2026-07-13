from worker.cloud_runner import run_cloud_job
from worker.pipeline_handlers import PipelineInputRequired


class FakeClient:
    def __init__(self):
        self.events = []
        self.jobs = {}

    def update_job(self, job_id, **fields):
        self.events.append(("update_job", job_id, fields))

    def update_product(self, product_id, **fields):
        self.events.append(("update_product", product_id, fields))

    def log(self, job_id, message, level="info"):
        self.events.append(("log", job_id, level, message))

    def enqueue_job_once(self, product_id, job_type, payload, idempotency_key, **options):
        self.jobs.setdefault(idempotency_key, {"type": job_type, "payload": payload})
        return self.jobs[idempotency_key]

    def list_product_assets(self, product_id):
        return []

    def get_product(self, product_id):
        return {"id": product_id, "partners_link": None}


class SuccessfulHandlers:
    def handle(self, job):
        return {"asset_id": "asset-1"}


class WaitingHandlers:
    def handle(self, job):
        raise PipelineInputRequired("ali_url_or_video", "영상 입력이 필요합니다")


def test_success_marks_job_complete_and_enqueues_one_next_stage():
    client = FakeClient()
    job = {
        "id": "job-video", "product_id": 4, "type": "source_video",
        "payload": {"orchestrated": True},
    }

    status = run_cloud_job(client, job, SuccessfulHandlers())

    assert status == "succeeded"
    assert any(event[0] == "update_job" and event[2]["status"] == "succeeded" for event in client.events)
    assert len(client.jobs) == 1
    assert next(iter(client.jobs.values()))["type"] == "analyze_video"


def test_input_boundary_keeps_job_waiting_and_does_not_enqueue():
    client = FakeClient()
    job = {"id": "job-video", "product_id": 4, "type": "source_video", "payload": {"orchestrated": True}}

    status = run_cloud_job(client, job, WaitingHandlers())

    assert status == "waiting_input"
    final = [event for event in client.events if event[0] == "update_job"][-1]
    assert final[2]["status"] == "waiting_input"
    assert final[2]["result"]["waiting_for"] == "ali_url_or_video"
    assert client.jobs == {}
