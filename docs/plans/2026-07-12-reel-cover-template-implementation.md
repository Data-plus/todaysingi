# 오늘의신기템 통일형 릴스 커버 구현 계획

설계 정본: `docs/plans/2026-07-12-reel-cover-template-design.md`

## 목표와 경계

여섯 영상 프레임에서 커버 후보를 추천하고, 대본 첫 두 문장으로 통일된
1080×1920 커버를 생성한다. 관리자는 온라인 상품 상세에서 후보와 문구를
수정하고 Worker 작업을 요청할 수 있다. 원본 `final.mp4`는 보존하며 Instagram
게시에는 커버가 붙은 `publish.mp4`와 정확한 `thumb_offset`을 사용한다.

## 1. 실패하는 커버 생성 테스트

파일:

- 추가: `tests/test_make_cover.py`

작업:

- [ ] SRT 첫 두 블록 문구 추출 테스트
- [ ] script 첫 두 문장 폴백 테스트
- [ ] 문구 누락·과도한 길이 거부 테스트
- [ ] 검은 픽셀 비율, 밝기, 대비, 선명도 점수 테스트
- [ ] 추천 프레임과 명시적 `--frame` 우선순위 테스트
- [ ] 픽셀 폭 기준 한글 줄바꿈 테스트
- [ ] 게시용 영상 FFmpeg 명령과 커버 시점 테스트
- [ ] `cover.json` 직렬화 테스트
- [ ] 구현 전 실패 확인

명령:

```text
python -m pytest tests/test_make_cover.py -q -p no:cacheprovider
```

## 2. 커버 생성 CLI

파일:

- 추가: `scripts/make_cover.py`
- 수정: `scripts/requirements.txt`

작업:

- [ ] Pillow를 명시적 런타임 의존성으로 추가
- [ ] 상품 작업 폴더와 여섯 후보를 검증
- [ ] SRT와 script에서 기본 문구 추출
- [ ] 후보 프레임을 정규화하고 품질 점수 계산
- [ ] 추천 또는 관리자 지정 프레임 선택
- [ ] 한글 Bold 폰트 탐색과 명확한 오류 구현
- [ ] 전체 화면 크롭, 하단 그라데이션, 두 색상 문구 합성
- [ ] `cover.jpg`를 임시 파일 후 원자적으로 교체
- [ ] `publish.mp4`를 별도 생성
- [ ] `cover.json`에 입력·점수·시점·템플릿 버전 기록
- [ ] `--frame`, `--line1`, `--line2`, `--cover-seconds` 제공

## 3. 샘플 상품 시각 E2E

파일:

- 생성하되 gitignore 유지: `ops/assets/2/cover.jpg`
- 생성하되 gitignore 유지: `ops/assets/2/publish.mp4`
- 생성하되 gitignore 유지: `ops/assets/2/cover.json`

작업:

- [ ] 상품 2 기본 추천 실행
- [ ] 여섯 점수와 추천 결과 확인
- [ ] 커버를 원본 해상도로 렌더링해 시각 검수
- [ ] 문구 위치, 그라데이션, 3:4 안전 영역 확인
- [ ] `publish.mp4` 길이와 마지막 커버 구간 확인
- [ ] 원본 `final.mp4` 체크섬 불변 확인

명령:

```text
python scripts/make_cover.py 2
```

## 4. Supabase migration 계약

파일:

- 추가: `supabase/migrations/202607120003_reel_covers.sql`
- 추가: `tests/test_reel_cover_migration.py`

작업:

- [ ] `jobs.type`에 `generate_cover` 추가
- [ ] `assets.kind`에 `cover_candidate`, `reel_cover` 추가
- [ ] `assets.metadata jsonb not null default '{}'` 추가
- [ ] 상품·kind·storage path 조회 인덱스 확인
- [ ] 기존 RLS와 bucket 정책 유지
- [ ] migration을 재실행해도 안전한 형태로 작성
- [ ] SQL 계약 테스트 통과

## 5. Worker 작업과 Storage 업로드

파일:

- 수정: `worker/control_plane.py`
- 수정: `worker/main.py` 필요 시
- 수정: `tests/test_control_plane.py`

작업:

- [ ] `generate_cover` payload의 frame 1~6 검증
- [ ] 두 문구의 타입·길이·개행 제한
- [ ] 인자 배열로 `make_cover.py` 명령 생성
- [ ] 성공 후 후보 여섯 장과 최종 커버를 private Storage에 upsert
- [ ] `assets` 행을 storage path 기준 멱등 upsert
- [ ] 후보 metadata에 frame, score, recommended 기록
- [ ] 최종 metadata에 selected frame, line1, line2, thumb offset 기록
- [ ] 비밀값이 로그에 노출되지 않게 유지
- [ ] Storage 실패 시 job 실패와 로컬 산출물 보존

## 6. 관리자 데이터 계층과 작업 요청

파일:

- 수정: `admin/src/types/admin.ts`
- 수정: `admin/src/lib/controlDesk.ts`
- 수정: `tests/test_admin_dashboard.py`

작업:

- [ ] asset metadata 타입 추가
- [ ] `cover_candidate`, `reel_cover` 분류 helper 추가
- [ ] private asset signed URL 생성
- [ ] 상품별 기본 훅과 추천 후보 파생
- [ ] `enqueueGenerateCover` 구현
- [ ] payload에 선택 프레임과 수정 문구 전달
- [ ] 같은 요청의 중복 클릭을 새 멱등 키와 busy 상태로 방지
- [ ] 생성 완료 후 데이터 새로고침

## 7. 상품 상세 커버 편집 UI

파일:

- 추가: `admin/src/components/CoverEditor.tsx`
- 수정: `admin/src/components/ProductDrawer.tsx`
- 수정: `admin/src/App.tsx`
- 수정: `admin/src/styles.css`

작업:

- [ ] 상품 상세에 `릴스 커버` 섹션 추가
- [ ] 여섯 후보를 3×2 그리드로 표시
- [ ] 추천·선택·키보드 focus 상태 구현
- [ ] 첫 줄과 두 번째 줄 입력, 글자수 안내 구현
- [ ] 최종 커버 9:16 미리보기 구현
- [ ] 후보 미업로드·Worker 오프라인·생성 중·실패·완료 상태 구현
- [ ] `커버 생성` 버튼을 실제 작업 enqueue에 연결
- [ ] 모바일 drawer에서 가로 스크롤 없이 동작
- [ ] 비활성 버튼에 이유 제공

## 8. Instagram 커버 시점 연결

파일:

- 수정: `scripts/publish_reel.py`
- 수정: `tests/test_publish_reel.py`

작업:

- [ ] `publish.mp4`가 있으면 게시 영상으로 우선 선택
- [ ] `cover.json`의 `thumbOffsetMs` 파싱·범위 검증
- [ ] 커버가 없을 때만 기존 밝기 기반 폴백 사용
- [ ] 계산된 `thumb_ms`를 `build_container_params`에 실제 전달
- [ ] dry-run에서 선택 파일과 커버 시점 출력
- [ ] `--thumb-offset` 명시값이 모든 자동값보다 우선
- [ ] 기존 게시 승인과 pipeline advance 유지

## 9. 전체 검증

작업:

- [ ] 커버 생성 순수 로직 테스트 통과
- [ ] migration·Worker·관리자·게시 회귀 테스트 통과
- [ ] 전체 Python 테스트 통과
- [ ] 관리자 TypeScript/Vite 빌드 통과
- [ ] 상품 2 커버 원본 해상도 시각 검수
- [ ] 데스크톱·모바일 관리자 편집 UI 검수
- [ ] 빌드와 로그에 비밀값이 없는지 확인
- [ ] 공개 링크 허브와 기존 릴스 영상 회귀 확인

명령:

```text
python -m pytest tests/ -q -p no:cacheprovider
npm --prefix admin run build
```

## 10. migration 적용과 배포

작업:

- [ ] 기능 브랜치를 원격에 push
- [ ] Supabase migration 적용
- [ ] Worker를 새 버전으로 재시작
- [ ] 상품 2 후보·최종 커버를 Storage에 업로드
- [ ] 관리자에서 후보 선택과 문구 수정 E2E
- [ ] main 병합과 Netlify 배포
- [ ] 운영 관리자에서 커버 편집과 상태 확인
- [ ] 실제 Instagram 재게시 같은 외부 부작용은 사용자 별도 승인 없이 실행하지 않음

## 완료 조건

- 상품별 커버가 동일한 구도·그라데이션·타이포 규칙을 따른다.
- 기본 문구와 프레임이 자동으로 준비되고 관리자가 수정할 수 있다.
- 생성 요청은 Worker가 꺼져 있어도 보존된다.
- Instagram API 게시가 생성된 커버 시점을 실제로 사용한다.
- 원본 영상과 기존 공개 사이트가 보존된다.
- 전체 테스트와 빌드가 통과한다.
