"""Supabase Storage 기반 원격 콘텐츠 단계 handler."""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Callable

from .asset_cleanup import cleanup_after_publish
from .llm import JsonLlmClient, content_prompt, validate_content_package
from .source_product import SourceInputRequired, fetch_coupang_product
from .storage_workspace import StorageWorkspace


CLOUD_PIPELINE_TYPES = {
    "source_product", "source_video", "analyze_video", "generate_script",
    "generate_voice", "compose_video", "generate_cover", "generate_caption",
    "publish_reel", "export_products",
}
ALI_VIDEO = re.compile(r"https://[^\"'\\\s]+?\.mp4(?:\?[^\"'\\\s]*)?", re.IGNORECASE)


class PipelineHandlerError(RuntimeError):
    pass


class PipelineInputRequired(PipelineHandlerError):
    def __init__(self, input_kind: str, prompt: str):
        super().__init__(prompt)
        self.input_kind = input_kind
        self.prompt = prompt


def _product_id(job: dict[str, Any]) -> int:
    value = job.get("product_id")
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise PipelineHandlerError("Cloud 콘텐츠 작업에는 product_id가 필요합니다")
    return value


def _job_id(job: dict[str, Any]) -> str:
    value = str(job.get("id") or "")
    if not value:
        raise PipelineHandlerError("Cloud 콘텐츠 작업 ID가 없습니다")
    return value


def _payload(job: dict[str, Any]) -> dict[str, Any]:
    return job.get("payload") if isinstance(job.get("payload"), dict) else {}


class CloudPipelineHandlers:
    def __init__(
        self,
        client,
        *,
        product_fetcher: Callable[[str], dict[str, Any]] = fetch_coupang_product,
        llm_client=None,
        instagram_publisher=None,
        session=None,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        temp_root: Path | None = None,
    ):
        self.client = client
        self.product_fetcher = product_fetcher
        self._llm_client = llm_client
        self.instagram_publisher = instagram_publisher
        if session is None:
            import requests
            session = requests.Session()
        self.session = session
        self.runner = runner
        self.temp_root = temp_root

    def handle(self, job: dict[str, Any]) -> dict[str, Any]:
        job_type = str(job.get("type") or "")
        if job_type not in CLOUD_PIPELINE_TYPES:
            raise PipelineHandlerError(f"지원하지 않는 Cloud 콘텐츠 작업입니다: {job_type}")
        handler = getattr(self, f"handle_{job_type}")
        return handler(job)

    def _product(self, job: dict[str, Any]) -> dict[str, Any]:
        product_id = _product_id(job)
        product = self.client.get_product(product_id)
        if not product:
            raise PipelineHandlerError("상품을 찾을 수 없습니다")
        return product

    def _assets(self, product_id: int, kind: str | None = None) -> list[dict[str, Any]]:
        rows = self.client.list_product_assets(product_id)
        if kind:
            rows = [row for row in rows if row.get("kind") == kind]
        return [row for row in rows if row.get("cleanup_status") != "deleted" and not row.get("deleted_at")]

    def _latest_asset(
        self, product_id: int, kind: str, *, filename: str | None = None,
    ) -> dict[str, Any]:
        rows = self._assets(product_id, kind)
        if filename:
            rows = [row for row in rows if str(row.get("storage_path") or "").endswith(f"/{filename}")]
        if not rows:
            raise PipelineHandlerError(f"필요한 {kind} asset이 없습니다")
        return rows[-1]

    def _llm(self):
        if self._llm_client is not None:
            return self._llm_client
        endpoint = os.environ.get("LLM_API_URL", "")
        api_key = os.environ.get("LLM_API_KEY", "")
        model = os.environ.get("LLM_MODEL", "")
        if not endpoint or not api_key or not model:
            raise PipelineInputRequired("llm_credentials", "Cloud Secret Manager에 LLM API 설정이 필요합니다.")
        self._llm_client = JsonLlmClient(endpoint, api_key, model, session=self.session)
        return self._llm_client

    def _run(self, command: list[str], *, timeout: int = 1800):
        completed = self.runner(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "command failed")[-1000:]
            raise PipelineHandlerError(detail)
        return completed

    def handle_source_product(self, job: dict[str, Any]) -> dict[str, Any]:
        product = self._product(job)
        payload = _payload(job)
        manual_title = str(payload.get("product_title") or "").strip()
        if manual_title:
            manual_image = str(payload.get("product_image_url") or "").strip() or product.get("image_url")
            if manual_image:
                parsed_image = urllib.parse.urlparse(str(manual_image))
                if parsed_image.scheme != "https" or not parsed_image.hostname:
                    raise PipelineHandlerError("상품 이미지 URL은 https:// 형식이어야 합니다")
            raw_price = payload.get("product_price", product.get("price"))
            try:
                manual_price = int(raw_price) if raw_price not in (None, "") else None
            except (TypeError, ValueError) as exc:
                raise PipelineHandlerError("상품 가격은 음수가 아닌 정수여야 합니다") from exc
            if manual_price is not None and manual_price < 0:
                raise PipelineHandlerError("상품 가격은 음수가 아닌 정수여야 합니다")
            sourced = {
                "title": manual_title[:300],
                "image_url": manual_image,
                "description": str(payload.get("product_description") or "").strip()[:5000],
                "price": manual_price,
            }
        else:
            coupang_url = str(payload.get("coupang_url") or product.get("coupang_url") or "")
            try:
                sourced = self.product_fetcher(coupang_url)
            except SourceInputRequired as exc:
                raise PipelineInputRequired("coupang_product", str(exc)) from exc
        snapshot = product.get("local_snapshot") if isinstance(product.get("local_snapshot"), dict) else {}
        snapshot = {**snapshot, "cloud": {"description": sourced.get("description", "")}}
        update = {
            "title": sourced["title"],
            "image_url": sourced.get("image_url"),
            "price": sourced.get("price"),
            "local_snapshot": snapshot,
        }
        self.client.update_product(_product_id(job), **update)
        return {"title": sourced["title"], "price": sourced.get("price"), "image_url": sourced.get("image_url")}

    @staticmethod
    def _validate_ali_url(value: str) -> str:
        parsed = urllib.parse.urlparse(value)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not (
            hostname == "aliexpress.com" or hostname.endswith(".aliexpress.com")
        ):
            raise PipelineHandlerError("AliExpress https URL만 사용할 수 있습니다")
        return parsed.geturl()

    def _download_ali(self, url: str, destination: Path):
        ali_url = self._validate_ali_url(url)
        try:
            page = self.session.get(
                ali_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; todaysingi-video-source/1.0)"},
                timeout=30,
            )
            if page.status_code < 400:
                text = page.text.replace("\\u002F", "/").replace("\\/", "/")
                match = ALI_VIDEO.search(text)
                if match:
                    video = self.session.get(match.group(0), headers={"Referer": ali_url}, timeout=120)
                    if video.status_code < 400 and video.content:
                        destination.write_bytes(video.content)
                        return
        except Exception:
            pass
        completed = self.runner(
            [sys.executable, "-m", "yt_dlp", "-o", str(destination), "-f", "mp4/best", ali_url],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )
        if completed.returncode != 0 or not destination.exists():
            raise PipelineInputRequired(
                "ali_url_or_video",
                "AliExpress 영상을 자동으로 받지 못했습니다. 다른 Ali URL을 넣거나 원본 MP4를 업로드하세요.",
            )

    def _duration(self, path: Path) -> float:
        completed = self._run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(path),
        ], timeout=60)
        try:
            return float(json.loads(completed.stdout)["format"]["duration"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PipelineHandlerError("영상 길이를 확인하지 못했습니다") from exc

    def handle_source_video(self, job: dict[str, Any]) -> dict[str, Any]:
        product = self._product(job)
        product_id = _product_id(job)
        payload = _payload(job)
        uploaded_asset_id = str(payload.get("uploaded_asset_id") or "")
        ali_url = str(payload.get("ali_url") or product.get("ali_url") or "")
        if not uploaded_asset_id and not ali_url:
            raise PipelineInputRequired(
                "ali_url_or_video",
                "AliExpress URL을 붙여 넣거나 원본 MP4를 업로드하세요.",
            )
        with StorageWorkspace(self.client, product_id, _job_id(job), temp_root=self.temp_root) as workspace:
            raw_output = workspace.output_path("raw.mp4")
            raw_asset = None
            if uploaded_asset_id:
                raw_asset = self.client.get_asset(uploaded_asset_id)
                if not raw_asset or raw_asset.get("product_id") != product_id:
                    raise PipelineHandlerError("업로드한 원본 영상 asset을 찾을 수 없습니다")
                raw_path = workspace.download_input(raw_asset, "raw.mp4")
            else:
                self._download_ali(ali_url, raw_output)
                raw_path = raw_output
                raw_asset = workspace.register_output(raw_output, kind="raw_video", retention_class="ephemeral")
                self.client.update_product(product_id, ali_url=ali_url)
            muted = workspace.output_path("muted.mp4")
            self._run(["ffmpeg", "-y", "-i", str(raw_path), "-c:v", "copy", "-an", str(muted)])
            duration = self._duration(muted)
            frame_pattern = str(workspace.outputs / "frame-%02d.jpg")
            self._run([
                "ffmpeg", "-y", "-i", str(muted), "-vf", f"fps=6/{duration}",
                "-frames:v", "6", frame_pattern,
            ])
            muted_asset = workspace.register_output(
                muted, kind="muted_video", retention_class="ephemeral",
                metadata={"duration_seconds": duration},
            )
            frame_assets = [
                workspace.register_output(
                    frame, kind="frame", retention_class="ephemeral",
                    metadata={"frame": index},
                )
                for index, frame in enumerate(sorted(workspace.outputs.glob("frame-*.jpg")), start=1)
            ]
            if len(frame_assets) != 6:
                raise PipelineHandlerError("영상 프레임 여섯 장을 만들지 못했습니다")
            return {
                "raw_asset_id": raw_asset.get("id") if raw_asset else None,
                "muted_asset_id": muted_asset.get("id"),
                "frame_asset_ids": [asset.get("id") for asset in frame_assets],
                "duration_seconds": duration,
            }

    def handle_analyze_video(self, job: dict[str, Any]) -> dict[str, Any]:
        product_id = _product_id(job)
        frames = self._assets(product_id, "frame")[-6:]
        if not frames:
            raise PipelineHandlerError("분석할 영상 프레임이 없습니다")
        with StorageWorkspace(self.client, product_id, _job_id(job), temp_root=self.temp_root) as workspace:
            images = []
            for index, asset in enumerate(frames, start=1):
                frame = workspace.download_input(asset, f"frame-{index:02d}.jpg")
                images.append("data:image/jpeg;base64," + base64.b64encode(frame.read_bytes()).decode("ascii"))
            analysis = self._llm().generate_json(
                "여섯 프레임의 장면 순서, 제품 동작, 눈에 띄는 변화, 과장하면 안 되는 불확실한 점을 JSON으로 분석하세요.",
                image_data_urls=images,
            )
            output = workspace.output_path("analysis.json")
            output.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
            asset = workspace.register_output(output, kind="metrics", retention_class="keep")
            return {"analysis_asset_id": asset.get("id"), "analysis_path": asset.get("storage_path")}

    def handle_generate_script(self, job: dict[str, Any]) -> dict[str, Any]:
        product_id = _product_id(job)
        product = self._product(job)
        analysis_asset = self._latest_asset(product_id, "metrics", filename="analysis.json")
        with StorageWorkspace(self.client, product_id, _job_id(job), temp_root=self.temp_root) as workspace:
            analysis_path = workspace.download_input(analysis_asset, "analysis.json")
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            snapshot = product.get("local_snapshot") if isinstance(product.get("local_snapshot"), dict) else {}
            cloud = snapshot.get("cloud") if isinstance(snapshot.get("cloud"), dict) else {}
            content = validate_content_package(self._llm().generate_json(content_prompt({
                "title": product.get("title"), "price": product.get("price"),
                "description": cloud.get("description", ""),
            }, analysis)))
            content_json = workspace.output_path("content.json")
            content_json.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
            script = workspace.output_path("script.txt")
            script.write_text(content["narration"], encoding="utf-8")
            package_asset = workspace.register_output(content_json, kind="script", retention_class="keep")
            script_asset = workspace.register_output(script, kind="script", retention_class="keep")
            return {
                "content_asset_id": package_asset.get("id"),
                "script_asset_id": script_asset.get("id"),
            }

    def handle_generate_voice(self, job: dict[str, Any]) -> dict[str, Any]:
        product_id = _product_id(job)
        script_asset = self._latest_asset(product_id, "script", filename="script.txt")
        api_key = os.environ.get("TYPECAST_API_KEY", "")
        if not api_key:
            raise PipelineInputRequired("typecast_credentials", "Cloud Secret Manager에 Typecast API key가 필요합니다.")
        payload = _payload(job)
        voice_id = str(payload.get("voice") or os.environ.get("TYPECAST_VOICE_ID", ""))
        if not voice_id:
            raise PipelineInputRequired("typecast_credentials", "게시용 Typecast voice ID를 설정해 주세요.")
        with StorageWorkspace(self.client, product_id, _job_id(job), temp_root=self.temp_root) as workspace:
            script_path = workspace.download_input(script_asset, "script.txt")
            voice_path = workspace.output_path("voice.mp3")
            try:
                from scripts.tts import synthesize_typecast
                from scripts.dub import generate_srt
            except ImportError as exc:
                raise PipelineHandlerError("Typecast 합성 모듈을 불러오지 못했습니다") from exc
            words = synthesize_typecast(
                script_path.read_text(encoding="utf-8"), voice_id,
                str(payload.get("rate") or "-5%"), voice_path, api_key,
                str(payload.get("emotion") or "toneup"), float(payload.get("intensity", 1)),
            )
            subtitle_path = workspace.output_path("subtitle.srt")
            subtitle_path.write_text(generate_srt(words), encoding="utf-8")
            voice_asset = workspace.register_output(voice_path, kind="voice", retention_class="ephemeral")
            subtitle_asset = workspace.register_output(subtitle_path, kind="subtitle", retention_class="keep")
            return {"voice_asset_id": voice_asset.get("id"), "subtitle_asset_id": subtitle_asset.get("id")}

    def handle_compose_video(self, job: dict[str, Any]) -> dict[str, Any]:
        product_id = _product_id(job)
        muted_asset = self._latest_asset(product_id, "muted_video")
        voice_asset = self._latest_asset(product_id, "voice")
        subtitle_asset = self._latest_asset(product_id, "subtitle")
        with StorageWorkspace(self.client, product_id, _job_id(job), temp_root=self.temp_root) as workspace:
            muted = workspace.download_input(muted_asset, "muted.mp4")
            voice = workspace.download_input(voice_asset, "voice.mp3")
            subtitle = workspace.download_input(subtitle_asset, "subtitle.srt")
            final = workspace.output_path("final.mp4")
            try:
                from scripts.dub import build_burn_cmd
            except ImportError as exc:
                raise PipelineHandlerError("영상 합성 모듈을 불러오지 못했습니다") from exc
            self._run(build_burn_cmd(str(muted), str(voice), str(subtitle), str(final)))
            asset = workspace.register_output(final, kind="final_video", retention_class="review")
            return {"final_asset_id": asset.get("id"), "final_path": asset.get("storage_path")}

    def handle_generate_cover(self, job: dict[str, Any]) -> dict[str, Any]:
        product_id = _product_id(job)
        frames = self._assets(product_id, "frame")[-6:]
        content_asset = self._latest_asset(product_id, "script", filename="content.json")
        final_asset = self._latest_asset(product_id, "final_video", filename="final.mp4")
        if not frames:
            raise PipelineHandlerError("커버 후보 프레임이 없습니다")
        with StorageWorkspace(self.client, product_id, _job_id(job), temp_root=self.temp_root) as workspace:
            local_frames = [
                workspace.download_input(asset, f"frame-{index:02d}.jpg")
                for index, asset in enumerate(frames, start=1)
            ]
            content_path = workspace.download_input(content_asset, "content.json")
            content = json.loads(content_path.read_text(encoding="utf-8"))
            final = workspace.download_input(final_asset, "final.mp4")
            try:
                from scripts.make_cover import (
                    build_publish_cmd, find_font, recommend_frame, render_cover, select_frame,
                )
            except ImportError as exc:
                raise PipelineHandlerError("커버 생성 모듈을 불러오지 못했습니다") from exc
            recommended, scores = recommend_frame(local_frames)
            override = _payload(job).get("frame")
            selected_number = int(override) if override is not None else recommended
            selected = select_frame(local_frames, recommended, selected_number)
            lines = content.get("cover_lines") or []
            line1 = str(_payload(job).get("line1") or (lines[0] if len(lines) > 0 else ""))
            line2 = str(_payload(job).get("line2") or (lines[1] if len(lines) > 1 else ""))
            cover = workspace.output_path("cover.jpg")
            render_cover(selected, line1, line2, cover, font_path=find_font(os.environ.get("COVER_FONT")))
            duration = self._duration(final)
            publish = workspace.output_path("publish.mp4")
            self._run(build_publish_cmd(final, cover, publish))
            cover_asset = workspace.register_output(
                cover, kind="reel_cover", retention_class="keep",
                metadata={
                    "selectedFrame": selected_number,
                    "recommendedFrame": recommended,
                    "scores": scores,
                    "line1": line1,
                    "line2": line2,
                    "thumbOffsetMs": int(duration * 1000) + 100,
                },
            )
            publish_asset = workspace.register_output(
                publish, kind="final_video", retention_class="review",
                metadata={"withCover": True, "thumbOffsetMs": int(duration * 1000) + 100},
            )
            return {"cover_asset_id": cover_asset.get("id"), "publish_asset_id": publish_asset.get("id")}

    def handle_generate_caption(self, job: dict[str, Any]) -> dict[str, Any]:
        product_id = _product_id(job)
        content_asset = self._latest_asset(product_id, "script", filename="content.json")
        with StorageWorkspace(self.client, product_id, _job_id(job), temp_root=self.temp_root) as workspace:
            content_path = workspace.download_input(content_asset, "content.json")
            content = validate_content_package(json.loads(content_path.read_text(encoding="utf-8")))
            hashtags = " ".join(f"#{tag}" for tag in content.get("hashtags", []))
            caption_text = content["caption"] + (f"\n\n{hashtags}" if hashtags else "")
            caption = workspace.output_path("caption.txt")
            caption.write_text(caption_text, encoding="utf-8")
            asset = workspace.register_output(caption, kind="caption", retention_class="keep")
            return {"caption_asset_id": asset.get("id"), "caption_path": asset.get("storage_path")}

    def handle_publish_reel(self, job: dict[str, Any]) -> dict[str, Any]:
        if not job.get("approved_at"):
            raise PipelineHandlerError("Instagram 게시 승인이 없습니다")
        product_id = _product_id(job)
        final_assets = self._assets(product_id, "final_video")
        if not final_assets:
            raise PipelineHandlerError("게시할 최종 영상이 없습니다")
        final_asset = next(
            (asset for asset in reversed(final_assets) if asset.get("metadata", {}).get("withCover")),
            final_assets[-1],
        )
        caption_asset = self._latest_asset(product_id, "caption", filename="caption.txt")
        video_url = self.client.create_signed_asset_url(final_asset, expires_in=3600)
        with StorageWorkspace(self.client, product_id, _job_id(job), temp_root=self.temp_root) as workspace:
            caption_path = workspace.download_input(caption_asset, "caption.txt")
            if self.instagram_publisher is None:
                try:
                    from .instagram import publish_reel_from_url
                except ImportError as exc:
                    raise PipelineHandlerError("Instagram 게시 모듈을 불러오지 못했습니다") from exc
                publisher = publish_reel_from_url
            else:
                publisher = self.instagram_publisher
            published = publisher(
                video_url=video_url,
                caption=caption_path.read_text(encoding="utf-8"),
                thumb_offset_ms=(final_asset.get("metadata") or {}).get("thumbOffsetMs"),
                session=self.session,
            )
        media_id = str(published.get("media_id") or "")
        permalink = str(published.get("permalink") or "")
        if not media_id or not permalink:
            raise PipelineHandlerError("Instagram 게시 결과에 media ID 또는 permalink가 없습니다")
        self.client.update_product(product_id, ig_media_id=media_id, reel_url=permalink, stage="published")
        cleanup = cleanup_after_publish(
            self.client,
            self.client.list_product_assets(product_id),
            published_media_id=media_id,
        )
        return {"media_id": media_id, "permalink": permalink, "cleanup": cleanup}

    def handle_export_products(self, job: dict[str, Any]) -> dict[str, Any]:
        product = self._product(job)
        if not product.get("partners_link"):
            raise PipelineInputRequired("partners_link", "쿠팡 파트너스 링크를 입력해 주세요.")
        hook = os.environ.get("NETLIFY_BUILD_HOOK_URL", "")
        if not hook.startswith("https://"):
            raise PipelineInputRequired("partners_link", "Netlify build hook 설정이 필요합니다.")
        response = self.session.post(hook, timeout=30)
        if response.status_code not in {200, 201, 202}:
            raise PipelineHandlerError(f"Netlify build hook 오류 {response.status_code}")
        return {"build_requested": True, "status_code": response.status_code}
