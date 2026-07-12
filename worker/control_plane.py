"""Supabase 작업 큐와 기존 CLI를 연결하는 로컬 Worker 핵심 로직."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Callable


STAGES = {
    "sourced", "video_ready", "script_ready", "audio_ready", "caption_ready",
    "published", "linked", "ads_running", "analyzed",
}
EMOTIONS = {"normal", "happy", "sad", "angry", "whisper", "toneup", "tonedown"}
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_RATE = re.compile(r"^[+-]\d{1,2}(?:\.\d+)?%$")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(TYPECAST_API_KEY|SUPABASE_SERVICE_ROLE_KEY|INSTAGRAM_ACCESS_TOKEN)"
    r"\s*[:=]\s*([^\s]+)"
)
BEARER_TOKEN = re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)([^\s]+)")


class ControlPlaneError(ValueError):
    pass


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def pipeline_product_row(item: dict[str, Any], *, now: dt.datetime | None = None) -> dict[str, Any]:
    """pipeline.json 아이템을 관리자 products 행으로 투영한다."""
    required = ("id", "title", "coupangUrl", "stage")
    missing = [key for key in required if key not in item]
    if missing:
        raise ControlPlaneError("pipeline 필수 필드 누락: " + ", ".join(missing))
    if not isinstance(item["id"], int) or item["id"] < 1:
        raise ControlPlaneError("pipeline id는 1 이상의 정수여야 합니다")
    if not isinstance(item["title"], str) or not item["title"].strip():
        raise ControlPlaneError("pipeline title이 비어 있습니다")
    if not isinstance(item["coupangUrl"], str) or not item["coupangUrl"].startswith("https://"):
        raise ControlPlaneError("pipeline coupangUrl이 올바르지 않습니다")
    if item["stage"] not in STAGES:
        raise ControlPlaneError(f"지원하지 않는 pipeline stage: {item['stage']}")

    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    stamp = (now or utc_now()).isoformat(timespec="seconds")
    row = {
        "id": item["id"],
        "title": item["title"].strip(),
        "coupang_url": item["coupangUrl"],
        "stage": item["stage"],
        "note": item.get("note", ""),
        "local_snapshot": {
            "history": item.get("history", []),
            "data": data,
        },
        "synced_at": stamp,
    }
    optional = {
        "aliUrl": "ali_url", "partnersLink": "partners_link", "reelUrl": "reel_url",
        "igMediaId": "ig_media_id", "siteProductId": "site_product_id",
    }
    for local_key, remote_key in optional.items():
        if local_key in data:
            row[remote_key] = data[local_key]
    return row


def redact_text(text: str, *, max_chars: int = 3500) -> str:
    """로그에서 알려진 비밀값과 bearer token을 제거한다."""
    clean = SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}=[REDACTED]", text or "")
    clean = BEARER_TOKEN.sub(lambda m: f"{m.group(1)}[REDACTED]", clean)
    return clean[:max_chars]


def _product_id(job: dict[str, Any]) -> int:
    product_id = job.get("product_id")
    if not isinstance(product_id, int) or product_id < 1:
        raise ControlPlaneError("작업 product_id는 1 이상의 정수여야 합니다")
    return product_id


def _https_url(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("https://"):
        raise ControlPlaneError(f"{name}은 https:// URL이어야 합니다")
    return value


def build_job_command(
    job: dict[str, Any], repo_root: Path, *, python_executable: str | None = None,
) -> list[str] | None:
    """허용된 payload만 subprocess 인자 배열로 변환한다."""
    job_type = job.get("type")
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    python = python_executable or sys.executable
    scripts = Path(repo_root) / "scripts"

    if job_type == "sync_pipeline":
        return None

    product_id = _product_id(job)
    if job_type == "create_product":
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise ControlPlaneError("create_product title이 올바르지 않습니다")
        coupang_url = _https_url(payload.get("coupang_url"), "coupang_url")
        command = [
            python, str(scripts / "pipeline.py"), "new", "--title", title.strip(),
            "--coupang-url", coupang_url,
        ]
        note = payload.get("note")
        if note:
            if not isinstance(note, str) or len(note) > 1000:
                raise ControlPlaneError("create_product note가 올바르지 않습니다")
            command.extend(["--note", note])
        return command

    if job_type == "dub":
        command = [python, str(scripts / "dub.py"), str(product_id), "--engine", "typecast"]
        voice = payload.get("voice")
        if voice is not None:
            if not isinstance(voice, str) or not SAFE_ID.fullmatch(voice):
                raise ControlPlaneError("허용되지 않는 voice 형식입니다")
            command.extend(["--voice", voice])
        emotion = payload.get("emotion")
        if emotion is not None:
            if emotion not in EMOTIONS:
                raise ControlPlaneError("허용되지 않는 emotion입니다")
            command.extend(["--emotion", emotion])
        if "intensity" in payload:
            intensity = payload["intensity"]
            if not isinstance(intensity, (int, float)) or isinstance(intensity, bool) or not 0 <= intensity <= 2:
                raise ControlPlaneError("intensity는 영 이상 이 이하여야 합니다")
            command.extend(["--intensity", str(intensity)])
        rate = payload.get("rate")
        if rate is not None:
            if not isinstance(rate, str) or not SAFE_RATE.fullmatch(rate):
                raise ControlPlaneError("허용되지 않는 rate 형식입니다")
            command.append(f"--rate={rate}")
        return command

    if job_type == "fetch_video":
        command = [python, str(scripts / "fetch_video.py"), str(product_id)]
        if payload.get("file"):
            file_path = Path(str(payload["file"]))
            if not file_path.is_absolute():
                raise ControlPlaneError("file은 절대 경로여야 합니다")
            command.extend(["--file", str(file_path)])
        elif payload.get("ali_url"):
            command.extend(["--ali-url", _https_url(payload["ali_url"], "ali_url")])
        else:
            raise ControlPlaneError("fetch_video에는 ali_url 또는 file이 필요합니다")
        return command

    if job_type == "generate_cover":
        command = [python, str(scripts / "make_cover.py"), str(product_id)]
        frame = payload.get("frame")
        if frame is not None:
            if not isinstance(frame, int) or isinstance(frame, bool) or not 1 <= frame <= 6:
                raise ControlPlaneError("frame은 일 이상 육 이하 정수여야 합니다")
            command.extend(["--frame", str(frame)])
        for key in ("line1", "line2"):
            value = payload.get(key)
            if value is None:
                continue
            if (not isinstance(value, str) or not value.strip() or len(value) > 60
                    or "\n" in value or "\r" in value):
                raise ControlPlaneError(f"{key} 커버 문구가 올바르지 않습니다")
            command.extend([f"--{key}", value.strip()])
        return command

    if job_type == "publish_reel":
        if not job.get("approved_at"):
            raise ControlPlaneError("Instagram 게시 승인이 필요합니다")
        return [python, str(scripts / "publish_reel.py"), str(product_id)]

    if job_type == "add_product":
        required = ("title", "price", "image", "link")
        if any(key not in payload for key in required):
            raise ControlPlaneError("add_product 필수 payload가 누락되었습니다")
        try:
            price = int(payload["price"])
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError("price는 정수여야 합니다") from exc
        if price < 0:
            raise ControlPlaneError("price는 음수일 수 없습니다")
        command = [
            python, str(scripts / "add_product.py"), "--title", str(payload["title"]),
            "--price", str(price), "--image", str(payload["image"]),
            "--link", _https_url(payload["link"], "link"),
        ]
        if payload.get("push") is True:
            command.append("--push")
        return command

    raise ControlPlaneError(f"지원하지 않는 작업 유형: {job_type}")


def cover_asset_specs(repo_root: Path, product_id: int, *, job_id: str | None = None) -> list[dict[str, Any]]:
    """로컬 커버 산출물을 Storage와 assets 행 사양으로 변환한다."""
    workdir = Path(repo_root) / "ops" / "assets" / str(product_id)
    metadata_path = workdir / "cover.json"
    cover_path = workdir / "cover.jpg"
    if not metadata_path.exists() or not cover_path.exists():
        raise ControlPlaneError("cover.json 또는 cover.jpg가 없습니다")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    scores = metadata.get("scores") if isinstance(metadata.get("scores"), dict) else {}
    recommended = metadata.get("recommendedFrame")
    specs = []
    for index, local_path in enumerate(sorted((workdir / "frames").glob("f*.jpg")), start=1):
        storage_path = f"covers/{product_id}/candidate-{index:02d}.jpg"
        score = scores.get(str(index)) if isinstance(scores.get(str(index)), dict) else {}
        specs.append({
            "local_path": local_path,
            "storage_path": storage_path,
            "row": {
                "product_id": product_id,
                "job_id": job_id,
                "kind": "cover_candidate",
                "storage_path": storage_path,
                "mime_type": "image/jpeg",
                "bytes": local_path.stat().st_size,
                "review_status": "pending",
                "metadata": {
                    "frame": index,
                    "score": score.get("score"),
                    "recommended": index == recommended,
                    "templateVersion": metadata.get("version"),
                },
            },
        })
    if not specs:
        raise ControlPlaneError("업로드할 커버 후보 프레임이 없습니다")
    storage_path = f"covers/{product_id}/cover.jpg"
    specs.append({
        "local_path": cover_path,
        "storage_path": storage_path,
        "row": {
            "product_id": product_id,
            "job_id": job_id,
            "kind": "reel_cover",
            "storage_path": storage_path,
            "mime_type": "image/jpeg",
            "bytes": cover_path.stat().st_size,
            "review_status": "pending",
            "metadata": {
                "selectedFrame": metadata.get("selectedFrame"),
                "recommendedFrame": recommended,
                "line1": metadata.get("line1"),
                "line2": metadata.get("line2"),
                "thumbOffsetMs": metadata.get("thumbOffsetMs"),
                "templateVersion": metadata.get("version"),
            },
        },
    })
    return specs


class ControlPlaneClient:
    def __init__(self, base_url: str, service_key: str, repo_root: Path, *, session=None):
        if not base_url.startswith("https://"):
            raise ControlPlaneError("SUPABASE_URL이 올바르지 않습니다")
        if not service_key:
            raise ControlPlaneError("SUPABASE_SERVICE_ROLE_KEY가 없습니다")
        if session is None:
            import requests
            session = requests.Session()
        self.base_url = base_url.rstrip("/")
        self.service_key = service_key
        self.repo_root = Path(repo_root)
        self.session = session

    def _request(self, method: str, path: str, *, json_body=None, prefer: str | None = None):
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        response = self.session.request(
            method, f"{self.base_url}/{path.lstrip('/')}", headers=headers,
            json=json_body, timeout=30,
        )
        if response.status_code >= 400:
            raise ControlPlaneError(f"Supabase {response.status_code}: {redact_text(response.text)}")
        if not response.content:
            return None
        return response.json()

    def _upload_file(self, bucket: str, storage_path: str, local_path: Path, mime_type: str):
        encoded_path = urllib.parse.quote(storage_path, safe="/")
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": mime_type,
            "x-upsert": "true",
        }
        response = self.session.request(
            "POST", f"{self.base_url}/storage/v1/object/{bucket}/{encoded_path}",
            headers=headers, data=Path(local_path).read_bytes(), timeout=60,
        )
        if response.status_code >= 400:
            raise ControlPlaneError(f"Storage {response.status_code}: {redact_text(response.text)}")

    def heartbeat(self, worker_id: str, *, status: str, current_job_id: str | None = None, version="0.1.0"):
        body = {
            "id": worker_id, "name": os.environ.get("COMPUTERNAME", worker_id),
            "status": status, "current_job_id": current_job_id, "version": version,
            "last_seen_at": utc_now().isoformat(timespec="seconds"),
        }
        return self._request(
            "POST", "rest/v1/workers?on_conflict=id", json_body=body,
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def claim_job(self, worker_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "POST", "rest/v1/rpc/claim_next_job",
            json_body={"p_worker_id": worker_id, "p_lock_seconds": 300},
        ) or []
        return rows[0] if rows else None

    def update_job(self, job_id: str, **fields):
        return self._request(
            "PATCH", f"rest/v1/jobs?id=eq.{job_id}", json_body=fields,
            prefer="return=minimal",
        )

    def log(self, job_id: str, message: str, level="info"):
        return self._request(
            "POST", "rest/v1/job_logs", json_body={
                "job_id": job_id, "level": level, "message": redact_text(message),
            }, prefer="return=minimal",
        )

    def sync_pipeline(self) -> int:
        path = self.repo_root / "ops" / "pipeline.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = [pipeline_product_row(item) for item in data.get("items", [])]
        if rows:
            self._request(
                "POST", "rest/v1/products?on_conflict=id", json_body=rows,
                prefer="resolution=merge-duplicates,return=minimal",
            )
        return len(rows)

    def sync_cover_assets(self, product_id: int, *, job_id: str | None = None) -> dict[str, Any]:
        specs = cover_asset_specs(self.repo_root, product_id, job_id=job_id)
        for spec in specs:
            self._upload_file(
                "completed-assets", spec["storage_path"], spec["local_path"],
                spec["row"]["mime_type"],
            )
        self._request(
            "POST", "rest/v1/assets?on_conflict=storage_path",
            json_body=[spec["row"] for spec in specs],
            prefer="resolution=merge-duplicates,return=minimal",
        )
        final_metadata = specs[-1]["row"]["metadata"]
        return {
            "cover_assets": len(specs),
            "cover_path": specs[-1]["storage_path"],
            "thumb_offset_ms": final_metadata.get("thumbOffsetMs"),
        }


def run_claimed_job(
    client, job: dict[str, Any], repo_root: Path,
    *, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> None:
    """선점된 작업 하나를 실행하고 실패까지 control plane에 기록한다."""
    job_id = str(job["id"])
    try:
        client.update_job(job_id, status="running", progress=5, error_summary=None)
        client.log(job_id, f"작업 시작: {job.get('type')}")
        command = build_job_command(job, Path(repo_root))
        if command is None:
            synced = client.sync_pipeline()
            result = {"synced_products": synced}
        else:
            completed = runner(
                command, cwd=str(repo_root), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=1800,
            )
            if completed.stdout:
                client.log(job_id, redact_text(completed.stdout))
            if completed.stderr:
                client.log(job_id, redact_text(completed.stderr), "warning" if completed.returncode == 0 else "error")
            if completed.returncode != 0:
                message = redact_text(completed.stderr or completed.stdout or f"exit {completed.returncode}")
                raise ControlPlaneError(message)
            cover_result = {}
            if job.get("type") == "generate_cover":
                client.update_job(job_id, progress=80)
                cover_result = client.sync_cover_assets(_product_id(job), job_id=job_id)
            synced = client.sync_pipeline()
            result = {"exit_code": completed.returncode, "synced_products": synced, **cover_result}
        client.update_job(
            job_id, status="succeeded", progress=100, result=result,
            lock_expires_at=None, finished_at=utc_now().isoformat(timespec="seconds"),
        )
        client.log(job_id, "작업 완료")
    except Exception as exc:  # Worker는 한 작업 실패로 종료하지 않는다.
        message = redact_text(str(exc)) or exc.__class__.__name__
        client.log(job_id, message, "error")
        client.update_job(
            job_id, status="failed", error_summary=message, lock_expires_at=None,
            finished_at=utc_now().isoformat(timespec="seconds"),
        )
