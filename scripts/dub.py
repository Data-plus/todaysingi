#!/usr/bin/env python3
"""대본(script.txt)을 TTS로 읽어 무음 영상에 더빙 + 자막을 입힌다.

사용 예:
    python scripts/dub.py 1 [--voice ko-KR-SunHiNeural] [--rate "+0%"] [--no-subs]

입력: ops/assets/<id>/muted.mp4, script.txt
출력: voice.mp3, subs.srt, final.mp4 → 관제탑 audio_ready 갱신

TTS 엔진 경계는 synthesize() 하나 — Typecast 전환 시 이 함수만 교체한다.
edge-tts는 상업 라이선스가 불분명하므로 실제 게시 영상에는 쓰지 않는다(PoC 전용).
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline
import tts

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_ROOT = REPO_ROOT / "ops" / "assets"
CHARS_PER_SEC = 5  # 대본 권장 글자수 기준


def sec_to_timecode(seconds):
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def recommended_chars(duration_s):
    return int(duration_s * CHARS_PER_SEC)


def generate_srt(words, max_chars=14):
    """단어 타이밍 목록 → SRT 문자열. 문장부호(.?!) 또는 max_chars 초과에서 블록 분리."""
    if not words:
        return ""
    blocks = []
    current = []

    def flush():
        if current:
            text = " ".join(w["text"] for w in current)
            blocks.append((current[0]["start_s"], current[-1]["end_s"], text))
            current.clear()

    for w in words:
        candidate = " ".join([x["text"] for x in current] + [w["text"]])
        if current and len(candidate) > max_chars:
            flush()
        current.append(w)
        if w["text"].rstrip().endswith((".", "?", "!")):
            flush()
    flush()

    lines = []
    for i, (start, end, text) in enumerate(blocks, start=1):
        lines.append(f"{i}\n{sec_to_timecode(start)} --> {sec_to_timecode(end)}\n{text}\n")
    return "\n".join(lines)


def build_mux_cmd(video, audio, out):
    """자막 없이 오디오만 결합(재인코딩 없음)."""
    return ["ffmpeg", "-y", "-i", video, "-i", audio,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-shortest", out]


def build_burn_cmd(video, audio, srt, out):
    """자막 번인 + 오디오 결합(비디오 재인코딩)."""
    style = ("FontSize=14,Bold=1,PrimaryColour=&HFFFFFF&,"
             "OutlineColour=&H000000&,Outline=2,MarginV=40")
    return ["ffmpeg", "-y", "-i", video, "-i", audio,
            "-map", "0:v", "-map", "1:a",
            "-vf", f"subtitles={srt}:force_style='{style}'",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-shortest", out]


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="대본을 TTS 더빙 + 자막으로 영상에 입힌다")
    parser.add_argument("id", type=int)
    parser.add_argument("--engine", choices=["auto", "typecast", "edge"], default="auto",
                        help="auto: .env에 TYPECAST_API_KEY 있으면 typecast, 없으면 edge")
    parser.add_argument("--voice", default=None,
                        help="typecast: tc_... voice_id / edge: ko-KR-SunHiNeural 등")
    parser.add_argument("--rate", default="+0%")
    parser.add_argument("--no-subs", action="store_true")
    args = parser.parse_args(argv)

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("ffmpeg/ffprobe가 필요합니다. https://ffmpeg.org 설치 후 재실행하세요.",
              file=sys.stderr)
        return 1

    workdir = ASSETS_ROOT / str(args.id)
    muted = workdir / "muted.mp4"
    script = workdir / "script.txt"
    if not muted.exists():
        print(f"{muted} 가 없습니다. fetch_video.py를 먼저 실행하세요.", file=sys.stderr)
        return 1
    if not script.exists() or not script.read_text(encoding="utf-8").strip():
        print(f"{script} 가 비어 있습니다. 대본을 먼저 작성하세요.", file=sys.stderr)
        return 1

    text = script.read_text(encoding="utf-8").strip()
    voice_mp3 = workdir / "voice.mp3"
    api_key = tts.get_api_key()
    engine = tts.choose_engine(args.engine, api_key)
    print(f"TTS 생성 중 (engine={engine}, rate {args.rate})...")
    engine, used_voice, words = tts.synthesize(
        text, engine=engine, voice=args.voice, rate=args.rate,
        out_path=voice_mp3, api_key=api_key)

    video_len = probe_duration(muted)
    audio_len = probe_duration(voice_mp3)
    print(f"영상 {video_len:.1f}초 / 음성 {audio_len:.1f}초")
    if audio_len > video_len:
        over = audio_len - video_len
        print(f"음성이 영상보다 {over:.1f}초 깁니다. 대본을 약 "
              f"{recommended_chars(over)}자 줄이거나 --rate \"+10%\" 를 시도하세요.",
              file=sys.stderr)
        return 1

    srt = workdir / "subs.srt"
    if not words and not args.no_subs:
        print("경고: TTS가 타이밍 정보를 주지 않아 자막 없이 합성합니다.", file=sys.stderr)
    if args.no_subs or not words:
        cmd = build_mux_cmd("muted.mp4", "voice.mp3", "final.mp4")
    else:
        srt.write_text(generate_srt(words), encoding="utf-8")
        cmd = build_burn_cmd("muted.mp4", "voice.mp3", "subs.srt", "final.mp4")

    # Windows 경로(드라이브 콜론)가 subtitles 필터를 깨뜨리므로 작업 폴더에서 상대경로로 실행
    result = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr[-800:], file=sys.stderr)
        return 1

    final = workdir / "final.mp4"
    rel = final.relative_to(REPO_ROOT).as_posix()
    data = pipeline.load_data(pipeline.DEFAULT_FILE)
    pipeline.advance_item(data, args.id, to="audio_ready",
                          sets={"finalVideo": rel, "voice": used_voice,
                                "ttsEngine": engine})
    pipeline.save_data(pipeline.DEFAULT_FILE, data)
    print(f"완성: {final}")
    print(f"관제탑: [{args.id}] → 더빙합성(audio_ready)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
