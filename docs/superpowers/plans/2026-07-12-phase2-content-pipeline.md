# Phase 2 콘텐츠 파이프라인 구현 계획

> 스펙(`docs/superpowers/specs/2026-07-12-phase2-content-pipeline-design.md`)이 정본. 이 문서는 실행 순서와 수용 기준. (작성 세션 인라인 실행 전제)

**Goal:** 쿠팡 링크 → 더빙·자막 영상 + 캡션 반자동 라인 (fetch_video.py, dub.py, PLAYBOOK).

---

### Task A: 의존성 + 뼈대
- [ ] `scripts/requirements.txt` (edge-tts, yt-dlp, requests) 작성, `pip install -r`
- [ ] `.gitignore`에 `ops/assets/` 추가
- [ ] Commit: `chore: Phase 2 의존성 (edge-tts, yt-dlp, requests)`

### Task B: dub.py TDD (순수 로직 먼저)
- [ ] `tests/test_dub.py`: `sec_to_timecode`(0→00:00:00,000 / 61.32→00:01:01,320), `generate_srt`(14자 블록 분리·문장부호 경계·타임코드), `recommended_chars`(길이×5), `build_mute_cmd`/`build_burn_cmd`/`build_mux_cmd` 인자 검증
- [ ] 실패 확인 → `scripts/dub.py` 구현(synthesize=edge-tts 추상화, 길이 검사, cwd 전략) → 통과
- [ ] Commit: `feat: TTS 더빙+자막 합성 스크립트 (dub) TDD`

### Task C: fetch_video.py TDD
- [ ] `tests/test_fetch_video.py`: 알리 HTML 조각에서 mp4 URL 추출 정규식, 프레임 타임스탬프 계산(6장 균등), 명령 조립
- [ ] 실패 확인 → `scripts/fetch_video.py` 구현(전략 1~4, ffprobe 길이, 권장 글자수 출력, advance 호출) → 통과
- [ ] Commit: `feat: 알리 영상 수집·무음화·프레임 추출 (fetch_video) TDD`

### Task D: 통합 스모크
- [ ] ffmpeg로 3초 640x360 테스트영상 생성(ops/assets/999/muted.mp4 직접 배치, 장부에 999 아이템 임시 등록)
- [ ] 가짜 script.txt → `dub.py 999` 실행(edge-tts 실호출) → final.mp4 생성 + ffprobe로 오디오 트랙·자막 번인 확인(스트림 검사)
- [ ] 임시 아이템·에셋 정리, 전체 pytest
- [ ] Commit(수정분 있으면)

### Task E: PLAYBOOK + 마무리
- [ ] `docs/PLAYBOOK.md`: 7단계 명령어 수준 매뉴얼 + 대본·캡션 기준 + 트러블슈팅
- [ ] README에 Phase 2 한 줄 + PLAYBOOK 링크
- [ ] Commit → main 머지 → push
- [ ] 수용 기준: pytest 전체 통과, 스모크 final.mp4 재생 가능(비디오+오디오 스트림), E2E는 사용자 링크 제공 시 별도 실행
