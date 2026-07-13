#!/usr/bin/env python3
"""Cloud Run Job entrypoint for GA4, cleanup, and the remote media pipeline."""
from __future__ import annotations

import argparse
import os
import re
import sys

from .asset_cleanup import cleanup_expired_assets
from .cloud_runner import run_cloud_job
from .control_plane import ControlPlaneClient, ControlPlaneError
from .ga4_sync import sync_ga4
from .pipeline_handlers import CloudPipelineHandlers


def cloud_worker_id(environment=None) -> str:
    env = environment or os.environ
    execution = env.get("CLOUD_RUN_EXECUTION") or env.get("CLOUD_RUN_JOB") or "worker"
    task = env.get("CLOUD_RUN_TASK_INDEX", "0")
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", f"cloud-{execution}-{task}").strip("-")
    return safe[:128]


class CompositeHandlers:
    def __init__(self, client):
        self.client = client
        self.pipeline = CloudPipelineHandlers(client)

    def handle(self, job):
        if job.get("type") == "sync_ga4":
            payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
            return sync_ga4(self.client, payload)
        if job.get("type") == "cleanup_assets":
            return cleanup_expired_assets(self.client, self.client.list_expired_assets())
        return self.pipeline.handle(job)


def main(argv=None):
    parser = argparse.ArgumentParser(description="오늘의신기템 Cloud Run Worker")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--drain", action="store_true", help="Cloud queue를 빌 때까지 처리")
    mode.add_argument("--once", action="store_true", help="작업 하나만 처리")
    mode.add_argument("--sync-ga4", action="store_true", help="queue 없이 GA4를 즉시 동기화")
    mode.add_argument("--cleanup", action="store_true", help="만료 asset을 즉시 정리")
    parser.add_argument("--max-jobs", type=int, default=20)
    args = parser.parse_args(argv)
    if args.max_jobs < 1 or args.max_jobs > 100:
        parser.error("--max-jobs는 일 이상 백 이하여야 합니다")

    url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    worker_id = cloud_worker_id()
    if not url or not service_key:
        print("SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY가 필요합니다", file=sys.stderr)
        return 2

    client = None
    try:
        client = ControlPlaneClient(url, service_key, os.getcwd())
        client.heartbeat(worker_id, status="online", version=os.environ.get("WORKER_VERSION", "cloud-dev"))
        if args.sync_ga4:
            result = sync_ga4(client, {"days": 30})
            print(f"GA4 동기화 완료: {result['stored_rows']}개 행")
            return 0
        if args.cleanup:
            result = cleanup_expired_assets(client, client.list_expired_assets())
            print(f"asset 정리 완료: {result['deleted']}개 삭제, {result['pending']}개 보류")
            return 0

        handlers = CompositeHandlers(client)
        limit = 1 if args.once else args.max_jobs
        processed = 0
        while processed < limit:
            client.heartbeat(worker_id, status="online", version=os.environ.get("WORKER_VERSION", "cloud-dev"))
            job = client.claim_cloud_job(worker_id)
            if not job:
                break
            client.heartbeat(
                worker_id,
                status="busy",
                current_job_id=job["id"],
                version=os.environ.get("WORKER_VERSION", "cloud-dev"),
            )
            status = run_cloud_job(client, job, handlers)
            processed += 1
            print(f"{job['id']} {job['type']}: {status}")
        print(f"Cloud queue 처리 완료: {processed}개")
        return 0
    except ControlPlaneError as exc:
        print(f"Cloud Worker 오류: {exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            try:
                client.heartbeat(worker_id, status="offline", version=os.environ.get("WORKER_VERSION", "cloud-dev"))
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
