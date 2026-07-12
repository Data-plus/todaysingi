#!/usr/bin/env python3
"""영상 프레임과 대본으로 통일형 Instagram 릴스 커버를 만든다.

산출물은 원본 final.mp4를 건드리지 않고 상품 작업 폴더에 저장한다.

    python scripts/make_cover.py 2
    python scripts/make_cover.py 2 --frame 5
    python scripts/make_cover.py 2 --line1 "키링인 줄 알았죠?" --line2 "진짜 카메라입니다."
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline


REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_ROOT = REPO_ROOT / "ops" / "assets"
CANVAS = (1080, 1920)
TEMPLATE_VERSION = 1
MAX_HOOK_CHARS = 60
DEFAULT_COVER_SECONDS = 0.5
FONT_SIZE = 58
TEXT_LEFT = 64
TEXT_RIGHT = 64
TEXT_BOTTOM = 1540
WHITE = (255, 255, 255)
ACCENT = (245, 210, 106)


class CoverError(ValueError):
    pass


def normalize_copy(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def validate_hook(line1: str, line2: str) -> tuple[str, str]:
    lines = (normalize_copy(line1), normalize_copy(line2))
    if not all(lines):
        raise CoverError("커버 문구 두 줄이 모두 필요합니다")
    if any(len(line) > MAX_HOOK_CHARS for line in lines):
        raise CoverError(f"커버 문구는 줄마다 {MAX_HOOK_CHARS}자 이하여야 합니다")
    return lines


def parse_srt_hook(text: str) -> tuple[str, str] | None:
    blocks = re.split(r"\r?\n\s*\r?\n", (text or "").strip())
    captions = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        content = [line for line in lines if not line.isdigit() and "-->" not in line]
        if content:
            captions.append(normalize_copy(" ".join(content)))
        if len(captions) == 2:
            return captions[0], captions[1]
    return None


def script_sentences(text: str) -> list[str]:
    clean = normalize_copy(text)
    if not clean:
        return []
    sentences = [normalize_copy(match) for match in re.findall(r"[^.!?。！？]+[.!?。！？]?", clean)]
    return [sentence for sentence in sentences if sentence]


def extract_hook(workdir: Path) -> tuple[str, str]:
    srt = Path(workdir) / "subs.srt"
    if srt.exists():
        parsed = parse_srt_hook(srt.read_text(encoding="utf-8"))
        if parsed:
            return validate_hook(*parsed)
    script = Path(workdir) / "script.txt"
    if script.exists():
        sentences = script_sentences(script.read_text(encoding="utf-8"))
        if len(sentences) >= 2:
            return validate_hook(sentences[0], sentences[1])
    raise CoverError("subs.srt 또는 script.txt에서 커버 문구 두 줄을 찾지 못했습니다")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_frame(path: Path) -> dict[str, float]:
    with Image.open(path) as source:
        image = ImageOps.fit(source.convert("RGB"), (180, 320), method=Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(image)
    pixels = list(gray.getdata())
    brightness = sum(pixels) / len(pixels) / 255
    black_ratio = sum(value < 20 for value in pixels) / len(pixels)
    contrast = _clamp(ImageStat.Stat(gray).stddev[0] / 96)

    edges = gray.filter(ImageFilter.FIND_EDGES)
    sharpness = _clamp(math.sqrt(ImageStat.Stat(edges).var[0]) / 72)
    width, height = gray.size
    center = gray.crop((int(width * .2), int(height * .18), int(width * .8), int(height * .82)))
    center_edges = center.filter(ImageFilter.FIND_EDGES)
    center_detail = _clamp(math.sqrt(ImageStat.Stat(center_edges).var[0]) / 72)
    exposure = _clamp(1 - abs(brightness - .56) / .56)

    score = (
        exposure * .18
        + contrast * .20
        + sharpness * .24
        + center_detail * .38
        - black_ratio * .90
    )
    return {
        "score": round(score, 6),
        "black_ratio": round(black_ratio, 6),
        "brightness": round(brightness, 6),
        "contrast": round(contrast, 6),
        "sharpness": round(sharpness, 6),
        "center_detail": round(center_detail, 6),
    }


def recommend_frame(candidates: list[Path]) -> tuple[int, dict[str, dict[str, float]]]:
    if not candidates:
        raise CoverError("추천할 프레임이 없습니다")
    scores = {str(index): score_frame(path) for index, path in enumerate(candidates, start=1)}
    recommended = max(range(1, len(candidates) + 1), key=lambda index: scores[str(index)]["score"])
    return recommended, scores


def select_frame(candidates: list[Path], recommended: int, override: int | None) -> Path:
    selected = override if override is not None else recommended
    if selected < 1 or selected > len(candidates):
        raise CoverError(f"선택한 프레임 {selected}번이 없습니다")
    return candidates[selected - 1]


def find_font(explicit: str | None = None) -> Path:
    candidates = [
        explicit,
        "C:/Windows/Fonts/malgunbd.ttf",
        "C:/Windows/Fonts/NanumGothicBold.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    raise CoverError("한글 Bold 폰트를 찾지 못했습니다. --font로 TTF/TTC 경로를 지정하세요")


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 2) -> list[str]:
    clean = normalize_copy(text)
    if not clean:
        raise CoverError("빈 커버 문구는 표시할 수 없습니다")
    lines: list[str] = []
    current = ""
    for character in clean:
        candidate = current + character
        if current and font.getlength(candidate) > max_width:
            lines.append(current.rstrip())
            current = character.lstrip()
        else:
            current = candidate
    if current:
        lines.append(current.rstrip())
    if len(lines) > max_lines:
        raise CoverError(f"커버 문구가 {max_lines}줄을 넘습니다. 문구를 줄여주세요")
    if any(font.getlength(line) > max_width for line in lines):
        raise CoverError("커버 문구가 안전 영역 너비를 넘습니다")
    return lines


def render_cover(
    frame_path: Path,
    line1: str,
    line2: str,
    output: Path,
    *,
    font_path: Path,
) -> None:
    line1, line2 = validate_hook(line1, line2)
    with Image.open(frame_path) as source:
        canvas = ImageOps.fit(source.convert("RGB"), CANVAS, method=Image.Resampling.LANCZOS)

    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    gradient = ImageDraw.Draw(overlay)
    start_y = int(CANVAS[1] * .50)
    gradient_height = CANVAS[1] - start_y
    for y in range(start_y, CANVAS[1]):
        progress = (y - start_y) / max(1, gradient_height - 1)
        alpha = int(235 * (progress ** 1.35))
        gradient.line((0, y, CANVAS[0], y), fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)

    font = ImageFont.truetype(str(font_path), FONT_SIZE)
    max_width = CANVAS[0] - TEXT_LEFT - TEXT_RIGHT
    first_lines = wrap_text(line1, font, max_width=max_width, max_lines=2)
    second_lines = wrap_text(line2, font, max_width=max_width, max_lines=2)
    line_height = int(FONT_SIZE * 1.28)
    group_gap = 8
    total_height = line_height * (len(first_lines) + len(second_lines)) + group_gap
    y = TEXT_BOTTOM - total_height
    if y < 1190:
        raise CoverError("커버 문구가 안전 영역을 넘습니다. 문구를 줄여주세요")

    draw = ImageDraw.Draw(canvas)
    for text in first_lines:
        draw.text(
            (TEXT_LEFT, y), text, font=font, fill=WHITE,
            stroke_width=3, stroke_fill=(0, 0, 0, 210),
        )
        y += line_height
    y += group_gap
    for text in second_lines:
        draw.text(
            (TEXT_LEFT, y), text, font=font, fill=ACCENT,
            stroke_width=3, stroke_fill=(0, 0, 0, 220),
        )
        y += line_height

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.stem + ".tmp" + output.suffix)
    canvas.convert("RGB").save(temporary, format="JPEG", quality=92, optimize=True)
    temporary.replace(output)


def build_publish_cmd(
    final_video: str | Path,
    cover_image: str | Path,
    output: str | Path,
    *,
    cover_seconds: float = DEFAULT_COVER_SECONDS,
) -> list[str]:
    seconds = f"{cover_seconds:g}"
    filters = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,fps=30,setsar=1,format=yuv420p[v0];"
        "[1:v]scale=1080:1920,fps=30,setsar=1,format=yuv420p[cover];"
        "[v0][cover]concat=n=2:v=1:a=0[v];"
        f"[0:a]apad=pad_dur={seconds}[a]"
    )
    return [
        "ffmpeg", "-y", "-i", str(final_video),
        "-loop", "1", "-t", seconds, "-i", str(cover_image),
        "-filter_complex", filters,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-movflags", "+faststart", "-shortest", str(output),
    ]


def probe_duration(path: Path) -> float:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(completed.stdout)["format"]["duration"])


def thumb_offset_ms(final_duration: float, cover_seconds: float) -> int:
    return int(round((final_duration + cover_seconds / 2) * 1000))


def write_metadata(path: Path, metadata: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(metadata, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    temporary.replace(path)


def update_pipeline(item_id: int, workdir: Path, metadata: dict[str, Any]) -> None:
    if not pipeline.DEFAULT_FILE.exists():
        return
    data = pipeline.load_data(pipeline.DEFAULT_FILE)
    item = next((entry for entry in data.get("items", []) if entry.get("id") == item_id), None)
    if item is None:
        raise CoverError(f"관제탑에 id {item_id} 상품이 없습니다")
    item.setdefault("data", {}).update({
        "coverImage": (workdir / "cover.jpg").relative_to(REPO_ROOT).as_posix(),
        "publishVideo": (workdir / "publish.mp4").relative_to(REPO_ROOT).as_posix(),
        "thumbOffsetMs": metadata["thumbOffsetMs"],
        "coverFrame": metadata["selectedFrame"],
        "coverLine1": metadata["line1"],
        "coverLine2": metadata["line2"],
    })
    pipeline.save_data(pipeline.DEFAULT_FILE, data)


def generate_cover(
    item_id: int,
    *,
    frame_override: int | None = None,
    line1_override: str | None = None,
    line2_override: str | None = None,
    cover_seconds: float = DEFAULT_COVER_SECONDS,
    font_override: str | None = None,
) -> dict[str, Any]:
    workdir = ASSETS_ROOT / str(item_id)
    final_video = workdir / "final.mp4"
    if not final_video.exists():
        raise CoverError(f"{final_video}가 없습니다. dub.py를 먼저 실행하세요")
    candidates = sorted((workdir / "frames").glob("f*.jpg"))
    if not candidates:
        raise CoverError("커버 후보가 없습니다. fetch_video.py를 먼저 실행하세요")
    if not 0.2 <= cover_seconds <= 2.0:
        raise CoverError("커버 길이는 0.2초 이상 2.0초 이하여야 합니다")

    default_line1, default_line2 = extract_hook(workdir)
    line1, line2 = validate_hook(
        line1_override if line1_override is not None else default_line1,
        line2_override if line2_override is not None else default_line2,
    )
    recommended, scores = recommend_frame(candidates)
    selected_path = select_frame(candidates, recommended, frame_override)
    selected = candidates.index(selected_path) + 1

    cover_image = workdir / "cover.jpg"
    render_cover(selected_path, line1, line2, cover_image, font_path=find_font(font_override))
    final_duration = probe_duration(final_video)
    publish_video = workdir / "publish.mp4"
    temporary_video = workdir / "publish.tmp.mp4"
    command = build_publish_cmd(final_video, cover_image, temporary_video, cover_seconds=cover_seconds)
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        temporary_video.unlink(missing_ok=True)
        raise CoverError("게시용 영상 생성 실패: " + (completed.stderr or completed.stdout)[-600:])
    temporary_video.replace(publish_video)

    metadata: dict[str, Any] = {
        "version": TEMPLATE_VERSION,
        "recommendedFrame": recommended,
        "selectedFrame": selected,
        "sourceFrame": selected_path.name,
        "line1": line1,
        "line2": line2,
        "coverSeconds": cover_seconds,
        "thumbOffsetMs": thumb_offset_ms(final_duration, cover_seconds),
        "scores": scores,
    }
    write_metadata(workdir / "cover.json", metadata)
    update_pipeline(item_id, workdir, metadata)
    return metadata


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="통일형 Instagram 릴스 커버 생성")
    parser.add_argument("id", type=int)
    parser.add_argument("--frame", type=int, choices=range(1, 7), default=None)
    parser.add_argument("--line1", default=None)
    parser.add_argument("--line2", default=None)
    parser.add_argument("--cover-seconds", type=float, default=DEFAULT_COVER_SECONDS)
    parser.add_argument("--font", default=None, help="한글 Bold TTF/TTC 경로")
    args = parser.parse_args(argv)

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("ffmpeg/ffprobe가 필요합니다", file=sys.stderr)
        return 1
    try:
        metadata = generate_cover(
            args.id,
            frame_override=args.frame,
            line1_override=args.line1,
            line2_override=args.line2,
            cover_seconds=args.cover_seconds,
            font_override=args.font,
        )
    except (CoverError, OSError, subprocess.SubprocessError) as exc:
        print(f"커버 생성 실패: {exc}", file=sys.stderr)
        return 1

    print(f"추천 프레임: {metadata['recommendedFrame']}번")
    print(f"선택 프레임: {metadata['selectedFrame']}번")
    print(f"문구: {metadata['line1']} / {metadata['line2']}")
    print(f"커버: {ASSETS_ROOT / str(args.id) / 'cover.jpg'}")
    print(f"게시 영상: {ASSETS_ROOT / str(args.id) / 'publish.mp4'}")
    print(f"Instagram thumb_offset: {metadata['thumbOffsetMs']}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
