#!/usr/bin/env python3
"""TTS 엔진 경계 모듈.

- Typecast (상업 라이선스, 기본): .env의 TYPECAST_API_KEY가 있으면 자동 선택
- edge-tts (PoC 전용 폴백): 키가 없을 때만. 상업 라이선스 불분명 — 게시용 금지

음성 목록 조회:
    python scripts/tts.py --list-voices
"""
import asyncio
import base64
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"
TYPECAST_BASE = "https://api.typecast.ai/v1"
TYPECAST_MODEL = "ssfm-v30"
DEFAULT_EDGE_VOICE = "ko-KR-SunHiNeural"


def load_env(path=ENV_FILE):
    """KEY=VALUE 형식의 .env 파일 파서(표준 라이브러리만). 없으면 빈 dict."""
    env = {}
    path = Path(path)
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[key.strip()] = value
    return env


def get_api_key():
    """환경변수 우선, 없으면 .env 파일에서 TYPECAST_API_KEY."""
    return os.environ.get("TYPECAST_API_KEY") or load_env().get("TYPECAST_API_KEY", "")


def choose_engine(engine, api_key):
    if engine != "auto":
        return engine
    return "typecast" if api_key else "edge"


def rate_to_tempo(rate):
    """edge 스타일 '+10%' → Typecast audio_tempo 1.1"""
    s = rate.strip()
    if not s.endswith("%"):
        raise ValueError(f"rate 형식 오류(예: +10%): {rate}")
    return round(1.0 + float(s[:-1]) / 100.0, 3)


def to_words(api_words):
    """Typecast words 배열 → 내부 Word 형식 [{text, start_s, end_s}]"""
    return [{"text": w["text"], "start_s": w["start"], "end_s": w["end"]}
            for w in (api_words or [])]


def synthesize_edge(text, voice, rate, out_path):
    import edge_tts

    async def run():
        # edge-tts 7.x는 boundary 기본값이 문장 단위라 명시적으로 단어 단위를 요청한다
        communicate = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        words = []
        with open(out_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                    words.append({
                        "text": chunk["text"],
                        "start_s": chunk["offset"] / 10_000_000,
                        "end_s": (chunk["offset"] + chunk["duration"]) / 10_000_000,
                    })
        return words

    return asyncio.run(run())


EMOTION_PRESETS = ("normal", "happy", "sad", "angry", "whisper", "toneup", "tonedown")


def build_typecast_payload(text, voice, rate, emotion=None, intensity=1.0):
    payload = {
        "voice_id": voice,
        "text": text,
        "model": TYPECAST_MODEL,
        "language": "kor",
        "output": {"audio_format": "mp3", "audio_tempo": rate_to_tempo(rate)},
    }
    if emotion:
        if emotion not in EMOTION_PRESETS:
            raise ValueError(f"emotion은 {EMOTION_PRESETS} 중 하나여야 합니다")
        payload["prompt"] = {"emotion_type": "preset", "emotion_preset": emotion,
                             "emotion_intensity": intensity}
    return payload


def synthesize_typecast(text, voice, rate, out_path, api_key, emotion=None, intensity=1.0):
    import requests

    payload = build_typecast_payload(text, voice, rate, emotion, intensity)
    r = requests.post(f"{TYPECAST_BASE}/text-to-speech/with-timestamps",
                      headers={"X-API-KEY": api_key}, json=payload, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Typecast 오류 {r.status_code}: {r.text[:300]}")
    data = r.json()
    Path(out_path).write_bytes(base64.b64decode(data["audio"]))
    return to_words(data.get("words"))


def pick_typecast_voice(api_key):
    """--voice 미지정 시 /v2/voices에서 첫 음성을 고른다."""
    voices = list_typecast_voices(api_key)
    if not voices:
        raise RuntimeError("사용 가능한 Typecast 음성이 없습니다")
    v = voices[0]
    print(f"음성 자동 선택: {v.get('voice_name')} ({v['voice_id']}) — "
          f"다른 음성은 python scripts/tts.py --list-voices")
    return v["voice_id"]


def list_typecast_voices(api_key, model=TYPECAST_MODEL):
    import requests
    r = requests.get("https://api.typecast.ai/v2/voices",
                     headers={"X-API-KEY": api_key},
                     params={"model": model}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"voices 조회 실패 {r.status_code}: {r.text[:200]}")
    return r.json()


def synthesize(text, *, engine, voice, rate, out_path, api_key="", emotion=None, intensity=1.0):
    """엔진 디스패처. 반환: (사용한 엔진, 사용한 음성, words)"""
    if engine == "typecast":
        if not api_key:
            raise RuntimeError(".env에 TYPECAST_API_KEY가 없습니다 "
                               f"(위치: {ENV_FILE})")
        if not voice:
            voice = pick_typecast_voice(api_key)
        words = synthesize_typecast(text, voice, rate, out_path, api_key,
                                    emotion, intensity)
    else:
        voice = voice or DEFAULT_EDGE_VOICE
        print("경고: edge-tts는 PoC 전용입니다(상업 라이선스 불분명). "
              "게시용 영상은 Typecast로 다시 생성하세요.", file=sys.stderr)
        words = synthesize_edge(text, voice, rate, out_path)
    return engine, voice, words


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import argparse
    parser = argparse.ArgumentParser(description="TTS 유틸리티")
    parser.add_argument("--list-voices", action="store_true")
    args = parser.parse_args(argv)
    if args.list_voices:
        key = get_api_key()
        if not key:
            print(f"TYPECAST_API_KEY가 없습니다. {ENV_FILE} 에 넣어주세요.", file=sys.stderr)
            return 1
        for v in list_typecast_voices(key):
            print(f"{v['voice_id']}  {v.get('voice_name','?'):<16} "
                  f"{v.get('gender','?'):<7} {v.get('age','?')}")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
