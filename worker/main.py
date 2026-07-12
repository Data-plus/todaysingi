#!/usr/bin/env python3
"""필요할 때 켜는 오늘의신기템 로컬 작업 Worker."""
import argparse
import datetime as dt
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from control_plane import ControlPlaneClient, ControlPlaneError, run_claimed_job, utc_now


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_env(path=REPO_ROOT / ".env"):
    values = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values


def config():
    file_env = load_env()
    get = lambda key, default="": os.environ.get(key) or file_env.get(key, default)
    worker_id = get("TODAYSINGI_WORKER_ID", socket.gethostname().lower())
    return get("SUPABASE_URL"), get("SUPABASE_SERVICE_ROLE_KEY"), worker_id


def heartbeat_runner(client, worker_id, job_id):
    """긴 subprocess 동안 heartbeat와 작업 잠금을 갱신하는 runner."""
    def run(command, **kwargs):
        timeout = kwargs.pop("timeout", 1800)
        kwargs.pop("capture_output", None)
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs,
        )
        started = time.monotonic()
        while process.poll() is None:
            if time.monotonic() - started > timeout:
                process.kill()
                stdout, stderr = process.communicate()
                return subprocess.CompletedProcess(command, 124, stdout, stderr or "작업 시간 초과")
            client.heartbeat(worker_id, status="busy", current_job_id=job_id)
            lock_until = utc_now() + dt.timedelta(seconds=300)
            client.update_job(job_id, lock_expires_at=lock_until.isoformat(timespec="seconds"))
            time.sleep(10)
        stdout, stderr = process.communicate()
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    return run


def main(argv=None):
    parser = argparse.ArgumentParser(description="오늘의신기템 Supabase 작업 Worker")
    parser.add_argument("--once", action="store_true", help="작업 하나를 확인한 뒤 종료")
    parser.add_argument("--interval", type=int, default=10, help="대기 시 polling 초")
    parser.add_argument("--sync", action="store_true", help="시작할 때 pipeline.json 동기화")
    args = parser.parse_args(argv)
    if args.interval < 2 or args.interval > 300:
        parser.error("--interval은 이 초 이상 삼백 초 이하여야 합니다")

    url, key, worker_id = config()
    try:
        client = ControlPlaneClient(url, key, REPO_ROOT)
        client.heartbeat(worker_id, status="online")
        if args.sync:
            count = client.sync_pipeline()
            print(f"pipeline 동기화: {count}개")
        while True:
            client.heartbeat(worker_id, status="online")
            job = client.claim_job(worker_id)
            if job:
                client.heartbeat(worker_id, status="busy", current_job_id=job["id"])
                print(f"작업 시작: {job['id']} ({job['type']})")
                run_claimed_job(
                    client, job, REPO_ROOT,
                    runner=heartbeat_runner(client, worker_id, job["id"]),
                )
                client.heartbeat(worker_id, status="online")
            elif args.once:
                print("대기 작업이 없습니다")
                break
            else:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Worker 종료")
    except ControlPlaneError as exc:
        print(f"Worker 오류: {exc}", file=sys.stderr)
        return 1
    finally:
        if "client" in locals():
            try:
                client.heartbeat(worker_id, status="offline")
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
