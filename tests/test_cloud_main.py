from worker.cloud_main import cloud_worker_id


def test_cloud_worker_id_is_stable_safe_and_bounded():
    value = cloud_worker_id({
        "CLOUD_RUN_JOB": "todaysingi-worker",
        "CLOUD_RUN_EXECUTION": "todaysingi-worker-abc/unsafe",
        "CLOUD_RUN_TASK_INDEX": "0",
    })
    assert value == "cloud-todaysingi-worker-abc-unsafe-0"
    assert len(value) <= 128
