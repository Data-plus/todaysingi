# Cloud Run 원격 파이프라인과 GA4 연동 설계

날짜: 2026-07-13  
상태: 사용자 승인됨

## 목적

오늘의신기템 콘텐츠 파이프라인을 로컬 PC와 수동 명령 실행에서 분리한다.
관리자가 어디서든 쿠팡 URL을 등록하면 원격 Worker가 상품·영상·대본·음성·자막·
커버·캡션을 준비하고, 관리자의 최종 승인을 받은 뒤 Instagram 릴스를 게시한다.

동시에 공개 링크 허브가 보내고 있는 GA4 이벤트를 서버 측 Data API와 연결해
관리자 성과 화면에 실제 방문·세션·상품 클릭 데이터를 표시한다.

## 확정 요구사항

- 실행 환경은 Supabase와 Cloud Run Job을 중심으로 구성한다.
- GitHub Actions는 테스트와 배포에만 사용하고 콘텐츠 처리 실행기로 사용하지 않는다.
- 로컬 PC가 꺼져 있어도 전체 콘텐츠 파이프라인이 진행돼야 한다.
- Instagram 실제 게시 직전에는 관리자 승인이 반드시 필요하다.
- 파이프라인 산출물은 비공개 Storage에 저장한다.
- 릴스 게시 성공 확인 후 영상·음성 파일은 삭제한다.
- 게시 실패나 중단 파일은 7일 보관한 뒤 자동 삭제한다.
- GA4는 최근 30일을 기본으로 표시하고 하루 한 번 자동 동기화한다.
- 관리자는 GA4 동기화를 즉시 요청할 수 있다.

## 현재 구조와 해결할 제약

현재 Worker는 저장소의 `ops/pipeline.json`과 `ops/assets/<id>/`를 직접 읽고 쓴다.
이 파일들은 Git에 포함되지 않으므로 매번 새 컨테이너로 실행되는 원격 Worker에서
그대로 사용할 수 없다. `publish_reel.py` 또한 최종 영상을 `site/media/`에 복사해
Git commit과 Netlify 배포로 공개 URL을 만든다.

관리자 성과 화면은 GA4 연결 상태와 상품 지표를 코드에서 항상 `연결 대기`와
`null`로 만들고 있다. 공개 사이트에는 Measurement ID `G-1C612TT8W0`과
`product_click` 전송 코드가 있으나 Data API 수집기는 없다.

따라서 다음 경계를 변경한다.

- Supabase DB: 파이프라인 상태의 진실 소스
- Supabase Storage: 비공개 작업 산출물의 진실 소스
- Cloud Run Job: Python·FFmpeg·브라우저 자동화 실행기
- Netlify: 공개 링크 허브와 관리자 정적 프런트엔드
- `pipeline.json`: 필요할 때 생성하는 로컬 내보내기·백업
- Git 저장소: 코드·프롬프트·DB migration·배포 설정만 저장

## 대안 비교

### GitHub Actions 단독

설정이 단순하고 공용 저장소의 표준 실행기는 무료지만 채택하지 않는다. 실행기
파일시스템은 작업마다 새로 만들어지고 미디어 산출물의 영속 저장소가 아니다. 또한
GitHub Actions는 저장소 소프트웨어의 빌드·테스트·배포와 무관한 작업 또는
서버리스 애플리케이션 실행 용도로 사용하지 않도록 제한한다. 콘텐츠 영상 처리의
주 실행기로 사용하는 것은 운영과 약관 양쪽에서 부적합하다.

### 상시 VPS 또는 백그라운드 Worker

기존 polling Worker를 거의 그대로 옮길 수 있지만 사용하지 않는 시간에도 서버를
운영해야 하고 OS 패치, 프로세스 복구, 방화벽, 디스크 정리를 직접 관리해야 한다.
필요할 때만 실행하려는 현재 운영 규모와 맞지 않는다.

### Supabase + Cloud Run Job

확정 방식이다. 작업이 있을 때 컨테이너를 시작하고 끝나면 종료한다. FFmpeg와
Playwright를 포함한 컨테이너를 사용할 수 있고, 실행 권한·런타임 비밀·배포 권한을
서로 다른 서비스 계정으로 분리할 수 있다.

## 시스템 구성

### 관리자와 Supabase

관리자는 기존 GitHub OAuth로 로그인한다. 생성·재시도·검수·게시 승인 같은 변경은
브라우저가 임의의 행을 직접 만드는 대신 관리자 확인이 포함된 RPC 또는 Edge
Function을 통해 수행한다.

관리자 동작으로 새 작업이 만들어지면 `enqueue-and-dispatch` Edge Function이
Supabase JWT와 관리자 권한을 확인하고 Cloud Run dispatcher를 호출한다. dispatcher는
같은 JWT의 issuer, audience, subject와 관리자 이메일을 다시 검증한다. 유효한 요청만
Cloud Run Job 실행 API로 전달한다.

dispatcher의 서비스 계정은 지정된 Worker Job을 실행할 권한만 갖는다. Typecast,
Instagram, LLM, Supabase 비밀은 읽을 수 없다. 이를 통해 Supabase에 장기 GCP 개인키를
저장하지 않는다.

### Cloud Run Worker

Worker 컨테이너에는 Python, FFmpeg/ffprobe, Playwright Chromium과 필요한 최소
라이브러리를 포함한다. 실행되면 Supabase의 승인된 대기 작업을 원자적으로 선점하고,
새로 만들어진 후속 작업까지 큐가 비거나 관리자 입력·승인 단계에 도달할 때까지
처리한 뒤 종료한다.

기본 설정은 다음과 같다.

- task 수 1
- Cloud Run 자체 재시도 0
- 작업 제한 시간 60분
- 한 컨테이너의 동시 실행 1
- DB 작업 잠금과 heartbeat 유지
- 모든 subprocess 인자는 허용 목록과 형식 검증 후 배열로 전달

여러 실행이 동시에 시작돼도 `claim_next_job`의 행 잠금으로 같은 작업을 중복 실행하지
않는다. Instagram 게시와 광고처럼 외부 부작용이 있는 작업은 DB에서도
`max_attempts = 1`을 유지한다.

### GitHub Actions

GitHub Actions는 다음 작업에만 사용한다.

- Python·프런트엔드 테스트
- Docker 이미지 빌드와 취약점 검사
- Artifact Registry push
- Cloud Run Job·dispatcher 배포

Google Cloud 인증은 GitHub OIDC와 Workload Identity Federation을 사용한다. 장기
GCP 서비스 계정 키를 GitHub Secrets에 넣지 않는다. workflow는 `main`과 수동 배포로
제한하고 제삼자 action은 full commit SHA에 고정한다.

## 콘텐츠 처리 흐름

1. 관리자가 쿠팡 URL을 등록한다.
2. `source_product`가 상품명, 가격, 대표 이미지와 상품 정보를 수집한다.
3. `find_source_video`가 AliExpress 동일 상품과 영상 후보를 찾는다.
4. 영상 확보 후 `prepare_video`가 다운로드, 무음화, 세로 편집, 프레임 추출을 한다.
5. `generate_script`가 정본 프롬프트로 대본을 만든다.
6. `synthesize_voice`가 게시용 Typecast 음성을 만든다.
7. `compose_video`가 음성·자막을 합성한다.
8. `generate_cover`가 커버 후보와 추천안을 만든다.
9. `generate_caption`이 상품 정보와 대본으로 캡션을 만든다.
10. 상품은 `caption_ready`에서 멈추고 관리자 검수를 기다린다.
11. 관리자가 영상·대본·커버·캡션을 확인하고 게시를 승인한다.
12. `publish_reel`이 짧게 만료되는 서명 영상 URL로 Meta 컨테이너를 생성한다.
13. Meta 처리 완료 후 `media_publish`를 호출하고 media ID와 permalink를 저장한다.
14. 파트너스 링크가 있으면 공개 상품을 활성화하고 Netlify 배포를 트리거한다.
15. 게시 성공 산출물 정리 작업을 실행한다.

LLM 호출부는 provider adapter로 분리한다. 배포 시 Anthropic 또는 OpenAI 등 하나의
게시 허용 API 키를 Secret Manager에 설정한다. 키가 없거나 호출이 실패하면 임의의
대본을 만들지 않고 `입력 필요`로 전환한다. 프롬프트 정본은 기존 `prompts/`를 쓴다.

## 관리자 입력 폴백

AliExpress와 쿠팡 페이지는 로그인, 지역, JavaScript, 봇 차단에 따라 자동 수집이
실패할 수 있다. 자동화 실패를 전체 파이프라인 실패로 숨기지 않는다.

- 작업 상태 `waiting_input`을 추가한다.
- 관리자 상품 상세에 필요한 입력 종류와 실패 원인을 표시한다.
- AliExpress URL 직접 입력과 영상 파일 업로드를 지원한다.
- 입력이 들어오면 새 안전 작업을 만들고 Cloud Run을 다시 실행한다.
- 관리자 수정본은 원본 생성 결과와 구분해 이력을 남긴다.

쿠팡 파트너스 Reporting API 승인 전에는 파트너스 링크를 관리자 입력으로 받는다.
승인 후 같은 작업 경계 안에 링크 변환·주문 수집기를 추가한다.

## 산출물 저장과 삭제

`pipeline-assets` 비공개 bucket에 상품별 prefix를 사용한다.

```text
products/<id>/source/raw.mp4
products/<id>/prepared/muted.mp4
products/<id>/frames/f01.jpg
products/<id>/script/script.txt
products/<id>/voice/voice.mp3
products/<id>/final/final.mp4
products/<id>/cover/cover.jpg
products/<id>/caption/caption.txt
```

컨테이너는 작업 시작 시 필요한 파일만 임시 디스크로 내려받고 종료 전에 새 산출물을
Storage로 올린다. `assets` 행에는 storage path, 종류, 크기, checksum, 생성 작업,
보관 등급, `expires_at`, `deleted_at`을 기록한다.

### 게시 성공 파일

다음 조건을 모두 확인한 뒤 무거운 미디어를 삭제한다.

1. Meta 영상 처리가 완료됐다.
2. `media_publish`가 media ID를 반환했다.
3. permalink와 media ID가 DB에 저장됐다.
4. 상품 단계가 `published` 이상으로 커밋됐다.

삭제 대상은 raw, muted, 중간 영상, 음성, final/publish 영상이다. 선택한 커버,
대본, 캡션, 자막 텍스트, Meta ID, permalink, 작업 로그와 분석 데이터는 유지한다.

삭제 실패는 게시 실패로 바꾸지 않는다. 해당 asset을 `cleanup_pending`으로 남기고
`cleanup_assets`가 다시 삭제한다.

### 실패·중단 파일

실패나 취소 시 즉시 삭제하지 않고 `expires_at = now() + 7 days`로 설정한다. 이 기간에
관리자가 재시도하거나 파일을 내려받을 수 있다. 매일 실행되는 `cleanup_assets`가
만료된 객체를 삭제하고 DB에 삭제 시각을 남긴다. 검수 대기 중인 정상 상품 파일은
승인 전까지 자동 만료시키지 않는다.

## Instagram 게시 호스팅 변경

최종 영상을 더 이상 `site/media/`에 commit하지 않는다. Worker가 비공개 Storage의
final 영상을 제한 시간의 signed URL로 만들고 Meta가 해당 URL을 가져가게 한다.
Meta의 처리 완료와 게시 성공 전에는 객체를 삭제하지 않는다.

이 변경으로 영상 바이너리가 public Git 기록에 계속 쌓이지 않고, Netlify 배포를
기다리지 않아도 된다. 기존에 이미 공개된 `site/media/` 파일은 별도 정리 작업으로
다루며 이번 migration에서 자동 삭제하지 않는다.

## 공개 링크 허브 반영

Supabase의 공개 가능 상품 데이터에서 기존 `products.json` 스키마를 생성한다. Worker가
Git commit 권한을 갖지 않게 하기 위해 링크 연결 완료 시 Netlify build hook을 호출한다.
Netlify build가 서버 환경에서 활성 상품만 읽어 `site/products.json` 산출물을 만든다.
서비스되는 JSON 필드 `id/title/price/image/link/addedAt/active`는 변경하지 않는다.

## GA4 이벤트 수집 변경

기존 Measurement ID는 유지한다. 구매 링크 클릭 이벤트는 커스텀 `product_click` 대신
GA4 권장 전자상거래 이벤트 `select_item`을 전송한다.

```javascript
gtag("event", "select_item", {
  item_list_id: "todaysingi_link_hub",
  item_list_name: "todaysingi_link_hub",
  items: [{
    item_id: "003",
    item_name: "픽셀블럭 조명",
    affiliation: "todaysingi"
  }]
});
```

이 형식은 Data API의 `itemId`, `itemName`, `itemsClickedInList`와 직접 연결된다. 기존
`product_click`은 더 이상 새로 보내지 않지만 GA4에 남아 있는 전체 과거 이벤트는
삭제하지 않는다. 기존 형식은 item parameter를 정식 item scope로 보내지 않았으므로
정확한 상품별 추이는 새 이벤트 배포일부터 시작한다고 관리자에 표시한다.

## GA4 서버 수집

`sync_ga4` 작업이 Google Analytics Data API `runReport`를 호출한다. 브라우저가 Data
API를 직접 호출하지 않는다.

Cloud Run runtime 서비스 계정 이메일을 GA4 Property의 Viewer로 등록하고 Google
Application Default Credentials를 사용한다. JSON 개인키를 GitHub, Netlify, Supabase
또는 브라우저에 저장하지 않는다. 숫자형 GA4 Property ID는 비밀이 아닌 환경 변수로
관리한다.

수집 데이터는 다음 두 범주다.

- 날짜·상품별: item ID, item name, items clicked in list
- 날짜·유입별: sessions, active users, source/medium

`ga4_product_daily`와 `ga4_traffic_daily`에 날짜 기준 upsert하며 원시 사용자 ID, client
ID, IP 같은 사용자 단위 식별자는 저장하지 않는다. `integration_syncs`에는 마지막
시도, 마지막 성공, 조회 범위, 행 수, 오류 요약을 기록한다.

동기화는 다음 두 방식으로 실행한다.

- Cloud Scheduler가 매일 한 번 `sync_ga4`를 실행
- 관리자 성과 화면의 `GA4 새로고침`이 같은 작업을 즉시 요청

연결 상태는 마지막 성공 시각으로 계산한다.

- `connected`: 마지막 성공 26시간 이내
- `stale`: 마지막 성공 26시간 초과
- `error`: 최근 시도가 실패하고 이후 성공이 없음
- `waiting`: Property ID 또는 권한이 아직 없음

## 관리자 성과 화면

기본 조회 기간은 최근 30일이며 실제 저장 데이터만 표시한다.

- 활성 사용자
- 세션
- 상품 링크 클릭
- 날짜별 클릭 추이
- 상품별 클릭 수와 점유율
- 주요 source/medium
- 마지막 성공 동기화 시각
- GA4 연결·지연·오류 상태

주문, 매출, 수수료는 GA4로 추정하지 않는다. 쿠팡 Reporting API가 준비될 때까지
명확히 `연결 대기`로 유지한다. 광고비와 ROAS도 Meta 지표와 쿠팡 매출 양쪽이
연결되기 전에는 계산하지 않는다.

## 비밀과 권한 분리

- 브라우저: Supabase publishable/anon 키만 포함
- Supabase Edge: 관리자 JWT 검증과 작업 생성
- dispatcher 서비스 계정: 특정 Cloud Run Job 실행 권한만 보유
- deploy 서비스 계정: Artifact Registry push와 Cloud Run 배포 권한
- Worker runtime 서비스 계정: 지정 Secret Manager secret 읽기와 GA4 읽기
- GA4: Property Viewer
- Storage: private bucket, 관리자 signed URL과 Worker service key만 접근

Worker runtime secret은 TYPECAST API 키, Instagram 계정·토큰, LLM API 키,
Supabase 서버 키, Netlify build hook처럼 서버에서만 필요한 값이다. 값은 로그에
출력하지 않고 오류 메시지의 알려진 secret과 bearer token을 마스킹한다.

## 오류와 재시도

- 수집·다운로드·LLM·TTS·GA4 읽기: 일시 오류에 한해 최대 2회
- 입력 누락·봇 차단: `waiting_input`, 자동 재시도 없음
- Instagram 게시: 자동 재시도 없음, 관리자 재승인 필요
- DB 저장 전 외부 게시 성공: media ID를 idempotency 복구 기록으로 남겨 중복 게시 방지
- 파일 정리 실패: `cleanup_pending`, 게시 성공 상태 유지
- GA4 실패: 기존 집계 유지, 연결 상태만 stale/error로 변경
- Cloud Run 중단: 만료 잠금을 회수하되 부작용 작업은 자동 재실행하지 않음

## 테스트와 검증

### 단위·계약 테스트

- 작업 타입과 상태 전이, 관리자 승인, 활성 중복 작업 방지
- Storage path 검증과 보관 기한 계산
- 게시 성공 전 영상 삭제 금지
- 게시 성공 후 미디어 삭제와 텍스트·커버 유지
- 실패 파일 7일 보관과 cleanup idempotency
- `select_item` payload의 item ID와 item name
- GA4 응답의 날짜·상품별 upsert와 연결 상태 계산
- 주문·매출을 GA4로 채우지 않는 계약

### 컨테이너 검증

- Docker build
- FFmpeg/ffprobe와 Chromium smoke test
- 비밀 없는 dry-run Worker
- Supabase Storage 다운로드·업로드 E2E
- GA4 Data API 최소 보고서 읽기

### 안전한 실제 E2E

1. 새 테스트 상품으로 쿠팡 URL을 등록한다.
2. 자동 수집 또는 관리자 영상 업로드 폴백을 확인한다.
3. 영상·대본·커버·캡션이 관리자에 나타나는지 확인한다.
4. 게시 전에는 Instagram API가 호출되지 않았는지 확인한다.
5. 관리자가 승인하고 릴스가 한 번만 게시되는지 확인한다.
6. DB에 media ID와 permalink가 저장된 후 영상만 삭제되는지 확인한다.
7. 공개 사이트 상품과 GA4 `select_item` 전송을 확인한다.
8. GA4 동기화 후 관리자에 실제 클릭이 표시되는지 확인한다.

기존 게시 상품 `[003]`에는 게시 E2E를 다시 실행하지 않는다.

## 단계적 배포

1. GA4 이벤트·DB 집계·관리자 표시를 먼저 배포해 독립 검증한다.
2. Storage를 원격 산출물 진실 소스로 전환한다.
3. 기존 Python 명령을 container-safe job handler로 분리한다.
4. Cloud Run dispatcher와 Job을 배포하고 비게시 작업을 검증한다.
5. 관리자 검수·입력 폴백을 연결한다.
6. 새 테스트 상품으로 실제 게시와 사후 삭제를 검증한다.
7. 로컬 Worker를 비상 폴백으로만 남긴다.

## 외부 준비 사항

- Google Cloud 프로젝트와 결제 계정
- Google Analytics Data API 활성화
- 숫자형 GA4 Property ID
- Worker 서비스 계정을 GA4 Property Viewer로 추가
- 게시용 LLM API 키 하나
- Typecast와 Instagram 비밀을 Secret Manager로 이전
- 쿠팡 Reporting API는 승인된 뒤 별도 연결

## 범위 밖

- 승인되지 않은 쿠팡 주문·매출 값을 추정하는 기능
- Instagram 릴스의 자동 삭제·수정·무승인 재게시
- DM 또는 메신저 자동 발송
- 쿠팡·AliExpress의 봇 차단 우회
- 기존 public Git 기록에서 영상 파일을 제거하는 history rewrite

## 참고

- GitHub Actions 추가 약관: https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features
- Cloud Run Job: https://cloud.google.com/run/docs/create-jobs
- Cloud Run Job secret: https://docs.cloud.google.com/run/docs/configuring/jobs/secrets
- GA4 권장 이벤트: https://developers.google.com/analytics/devguides/collection/ga4/reference/events
- GA4 Data API schema: https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema
- GA4 Data API quickstart: https://developers.google.com/analytics/devguides/reporting/data/v1/quickstart
