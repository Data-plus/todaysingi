# Cloud Run 운영 런북

관리자에서 승인한 작업을 PC 없이 실행하는 운영 절차다. Cloud Run Job은 큐가 빌
때까지만 실행되고 끝나며, dispatcher 서비스도 최소 인스턴스가 0이므로 대기 중에는
실행 자원을 점유하지 않는다.

## 1. 운영 구성

- Supabase: 상품·작업·산출물·GA4 집계의 진실 소스
- pipeline-assets: 비공개 원본·중간·완성 파일 저장소
- Cloud Run Job todaysingi-worker: FFmpeg, Typecast, LLM, Instagram, GA4 처리
- Cloud Run Service todaysingi-dispatcher: 관리자 JWT를 다시 검증하고 Job 실행
- Supabase Edge Function dispatch-worker: 관리자 브라우저와 dispatcher 사이의 경계
- Cloud Scheduler: 매일 GA4 동기화와 만료 파일 정리
- GitHub Actions: OIDC/WIF로 이미지만 배포하며 장기 GCP 키는 저장하지 않음

Instagram 게시 성공은 DB에 ig_media_id와 reel_url이 저장된 시점이다. 그 뒤
원본·무음·프레임·음성·완성 영상은 삭제하고, 커버·대본·캡션·자막·분석 결과는
남긴다. 삭제 실패는 cleanup_pending으로 남겨 다음 정리 실행에서 다시 처리한다.
실패·취소된 임시 미디어만 7일 후 만료되며, 정상 검수 대기 파일은 자동 만료되지 않는다.

## 2. 변수 준비

PowerShell에서 실제 값으로 바꾼다. 비밀 값은 이 셸이나 GitHub 변수에 넣지 않는다.

~~~powershell
$PROJECT_ID = "Google Cloud 프로젝트 ID"
$REGION = "asia-northeast3"
$AR_REPOSITORY = "todaysingi"
$WORKER_JOB = "todaysingi-worker"
$DISPATCHER_SERVICE = "todaysingi-dispatcher"
$WORKER_SA = "todaysingi-worker@$PROJECT_ID.iam.gserviceaccount.com"
$DISPATCHER_SA = "todaysingi-dispatcher@$PROJECT_ID.iam.gserviceaccount.com"
$SCHEDULER_SA = "todaysingi-scheduler@$PROJECT_ID.iam.gserviceaccount.com"
$DEPLOY_SA = "todaysingi-github@$PROJECT_ID.iam.gserviceaccount.com"
$SUPABASE_URL = "https://프로젝트-ref.supabase.co"
$SUPABASE_ANON_KEY = "Supabase publishable 또는 anon key"
$ADMIN_EMAIL = "plusmg@gmail.com"
gcloud config set project $PROJECT_ID
~~~

## 3. Supabase 스키마 적용

저장소 루트에서 아래 명령을 실행한다. 적용 전 Supabase 대시보드의 Database
Backups 상태를 확인한다.

~~~powershell
npx supabase link --project-ref davyotbbhgnfxpgaglki
npx supabase db push
~~~

적용 후 SQL Editor에서 다음을 확인한다.

~~~sql
select id, type, status from public.jobs order by created_at desc limit 10;
select integration, status, last_success_at from public.integration_syncs;
select id, public, file_size_limit from storage.buckets where id = 'pipeline-assets';
~~~

pipeline-assets의 public 값은 반드시 false여야 한다.

## 4. Google Cloud 최초 구성

API와 Artifact Registry, 실행 서비스 계정을 만든다.

~~~powershell
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com iamcredentials.googleapis.com sts.googleapis.com analyticsdata.googleapis.com cloudscheduler.googleapis.com
gcloud artifacts repositories create $AR_REPOSITORY --repository-format=docker --location=$REGION --description="todaysingi containers"
gcloud iam service-accounts create todaysingi-worker --display-name="todaysingi worker"
gcloud iam service-accounts create todaysingi-dispatcher --display-name="todaysingi dispatcher"
gcloud iam service-accounts create todaysingi-scheduler --display-name="todaysingi scheduler"
gcloud iam service-accounts create todaysingi-github --display-name="todaysingi GitHub deploy"
~~~

Secret Manager에 아래 이름을 만들고 Google Cloud Console에서 값을 한 버전씩 넣는다.
명령행 인자나 셸 기록에 실제 값을 넣지 않는다.

- todaysingi-supabase-service-role
- todaysingi-typecast-api-key
- todaysingi-llm-api-key
- todaysingi-instagram-access-token
- todaysingi-netlify-build-hook

각 Secret에 worker 계정만 Secret Accessor를 부여한다.

~~~powershell
$SECRET_NAMES = @("todaysingi-supabase-service-role","todaysingi-typecast-api-key","todaysingi-llm-api-key","todaysingi-instagram-access-token","todaysingi-netlify-build-hook")
foreach ($name in $SECRET_NAMES) { gcloud secrets add-iam-policy-binding $name --member="serviceAccount:$WORKER_SA" --role="roles/secretmanager.secretAccessor" }
~~~

## 5. 첫 이미지와 Cloud Run 리소스

최초 한 번은 로컬에서 이미지를 올린다. 이후 main 배포는 GitHub Actions가 담당한다.

~~~powershell
$WORKER_IMAGE = "$REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPOSITORY/todaysingi-worker:bootstrap"
$DISPATCHER_IMAGE = "$REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPOSITORY/todaysingi-dispatcher:bootstrap"
gcloud auth configure-docker "$REGION-docker.pkg.dev"
docker build --tag $WORKER_IMAGE .
docker build --tag $DISPATCHER_IMAGE dispatcher
docker push $WORKER_IMAGE
docker push $DISPATCHER_IMAGE
~~~

아래 비밀이 아닌 값을 먼저 결정한다.

- GA4_PROPERTY_ID: G-로 시작하는 측정 ID가 아니라 숫자형 Property ID
- LLM_API_URL, LLM_MODEL: 사용하는 OpenAI 호환 JSON API와 모델
- TYPECAST_VOICE_ID: 게시에 사용할 Typecast voice ID
- INSTAGRAM_ACCOUNT_ID: Instagram 비즈니스 계정 ID
- INSTAGRAM_VIDEO_HOSTS: Supabase Storage signed URL의 호스트

Job은 Instagram 같은 외부 부작용을 중복 실행하지 않도록 Cloud Run 자체 재시도를 0으로
고정한다. 데이터베이스도 게시 작업의 max_attempts를 1로 제한한다.

~~~powershell
$WORKER_ENV = "SUPABASE_URL=$SUPABASE_URL,GA4_PROPERTY_ID=숫자ID,LLM_API_URL=https://호환-API,LLM_MODEL=모델명,TYPECAST_VOICE_ID=voice-id,INSTAGRAM_ACCOUNT_ID=계정ID,INSTAGRAM_VIDEO_HOSTS=프로젝트-ref.supabase.co,META_GRAPH_VERSION=v21.0,WORKER_VERSION=cloud-v1"
$WORKER_SECRETS = "SUPABASE_SERVICE_ROLE_KEY=todaysingi-supabase-service-role:latest,TYPECAST_API_KEY=todaysingi-typecast-api-key:latest,LLM_API_KEY=todaysingi-llm-api-key:latest,INSTAGRAM_ACCESS_TOKEN=todaysingi-instagram-access-token:latest,NETLIFY_BUILD_HOOK_URL=todaysingi-netlify-build-hook:latest"
gcloud run jobs create $WORKER_JOB --image=$WORKER_IMAGE --region=$REGION --service-account=$WORKER_SA --cpu=2 --memory=4Gi --task-timeout=3600s --max-retries=0 --set-env-vars=$WORKER_ENV --set-secrets=$WORKER_SECRETS
~~~

dispatcher의 Cloud Run 공개 진입은 허용하지만 애플리케이션이 Supabase JWT와 관리자 이메일을
모두 검증한다. 이 서비스에는 비밀 DB 키를 주지 않는다.

~~~powershell
$DISPATCHER_ENV = "SUPABASE_URL=$SUPABASE_URL,SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY,ADMIN_EMAIL=$ADMIN_EMAIL,GCP_PROJECT=$PROJECT_ID,GCP_REGION=$REGION,CLOUD_RUN_JOB=$WORKER_JOB"
gcloud run deploy $DISPATCHER_SERVICE --image=$DISPATCHER_IMAGE --region=$REGION --service-account=$DISPATCHER_SA --cpu=1 --memory=512Mi --min=0 --max=3 --concurrency=20 --set-env-vars=$DISPATCHER_ENV --allow-unauthenticated
gcloud run jobs add-iam-policy-binding $WORKER_JOB --region=$REGION --member="serviceAccount:$DISPATCHER_SA" --role="roles/run.invoker"
$DISPATCHER_URL = gcloud run services describe $DISPATCHER_SERVICE --region=$REGION --format="value(status.url)"
Invoke-RestMethod "$DISPATCHER_URL/healthz"
~~~

## 6. Edge Function 연결

dispatcher URL을 Supabase Function Secret에 넣고 배포한다.

~~~powershell
npx supabase secrets set CLOUD_DISPATCHER_URL=$DISPATCHER_URL
npx supabase functions deploy dispatch-worker
~~~

Supabase의 SUPABASE_URL과 SUPABASE_ANON_KEY 기본 Secret은 Edge Function 런타임이
제공한다. 관리자에서 상품 등록이나 GA4 새로고침을 누르면 queued 작업을 먼저 저장한 뒤
dispatcher를 호출한다. 호출 실패 시에도 작업은 사라지지 않으며 다음 호출에서 처리된다.

## 7. GA4 실제 데이터 연결

Google Analytics 관리 화면에서 다음을 수행한다.

1. 관리 → 속성 설정에서 숫자형 Property ID를 확인해 Job 환경변수에 넣는다.
2. 속성 액세스 관리에 worker 서비스 계정 이메일을 GA4 Property Viewer로 추가한다.
3. Google Analytics Data API가 프로젝트에서 활성화됐는지 확인한다.

첫 동기화를 실행한다.

~~~powershell
gcloud run jobs execute $WORKER_JOB --region=$REGION --args=--sync-ga4 --wait
~~~

관리자 성과 화면에 마지막 성공 시각, 클릭, 세션, 사용자, 상품·유입별 표가 표시되어야 한다.
주문·매출·수수료는 쿠팡 Reporting API 승인 전까지 연결 대기로 남는 것이 정상이다.

## 8. 매일 동기화와 7일 정리

Scheduler 계정에 Job 실행 권한을 주고 한국 시간 새벽에 두 작업을 실행한다.

~~~powershell
gcloud run jobs add-iam-policy-binding $WORKER_JOB --region=$REGION --member="serviceAccount:$SCHEDULER_SA" --role="roles/run.invoker"
$RUN_URI = "https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/$($WORKER_JOB):run"
gcloud scheduler jobs create http todaysingi-ga4-daily --location=$REGION --schedule="15 4 * * *" --time-zone="Asia/Seoul" --uri=$RUN_URI --http-method=POST --oauth-service-account-email=$SCHEDULER_SA --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform" --headers="Content-Type=application/json" --message-body='{"overrides":{"containerOverrides":[{"args":["--sync-ga4"]}]}}'
gcloud scheduler jobs create http todaysingi-assets-cleanup --location=$REGION --schedule="45 4 * * *" --time-zone="Asia/Seoul" --uri=$RUN_URI --http-method=POST --oauth-service-account-email=$SCHEDULER_SA --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform" --headers="Content-Type=application/json" --message-body='{"overrides":{"containerOverrides":[{"args":["--cleanup"]}]}}'
~~~

수동 정리 검증:

~~~powershell
gcloud run jobs execute $WORKER_JOB --region=$REGION --args=--cleanup --wait
~~~

## 9. GitHub OIDC/WIF 배포

장기 서비스 계정 JSON 키는 만들지 않는다. 저장소 Data-plus/todaysingi만 deploy 계정을
가장할 수 있도록 제한한다.

~~~powershell
$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
$POOL = "github"
$PROVIDER = "todaysingi"
gcloud iam workload-identity-pools create $POOL --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers create-oidc $PROVIDER --location=global --workload-identity-pool=$POOL --issuer-uri="https://token.actions.githubusercontent.com" --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" --attribute-condition="assertion.repository=='Data-plus/todaysingi'"
$PRINCIPAL = "principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/attribute.repository/Data-plus/todaysingi"
gcloud iam service-accounts add-iam-policy-binding $DEPLOY_SA --role="roles/iam.workloadIdentityUser" --member=$PRINCIPAL
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$DEPLOY_SA" --role="roles/run.admin"
gcloud artifacts repositories add-iam-policy-binding $AR_REPOSITORY --location=$REGION --member="serviceAccount:$DEPLOY_SA" --role="roles/artifactregistry.writer"
gcloud iam service-accounts add-iam-policy-binding $WORKER_SA --member="serviceAccount:$DEPLOY_SA" --role="roles/iam.serviceAccountUser"
gcloud iam service-accounts add-iam-policy-binding $DISPATCHER_SA --member="serviceAccount:$DEPLOY_SA" --role="roles/iam.serviceAccountUser"
$WIF_PROVIDER = "projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/providers/$PROVIDER"
~~~

GitHub 저장소 Settings → Environments에서 production 보호 규칙을 켜고, Actions
Variables에 다음 값을 넣는다. 모두 리소스 이름이며 비밀이 아니다.

- GCP_PROJECT_ID
- GCP_REGION
- GCP_ARTIFACT_REPOSITORY
- GCP_WORKLOAD_IDENTITY_PROVIDER
- GCP_DEPLOY_SERVICE_ACCOUNT
- CLOUD_RUN_WORKER_JOB
- CLOUD_RUN_DISPATCHER_SERVICE

main에 머지되면 고정 SHA 액션과 OIDC로 두 이미지를 올리고 기존 리소스의 이미지만 교체한다.

## 10. 운영 명령과 복구

~~~powershell
gcloud run jobs execute $WORKER_JOB --region=$REGION --args=--drain --wait
gcloud run jobs executions list --job=$WORKER_JOB --region=$REGION
gcloud run jobs executions logs read --job=$WORKER_JOB --region=$REGION --limit=100
gcloud run services logs read $DISPATCHER_SERVICE --region=$REGION --limit=100
~~~

- queued가 남음: 관리자에서 재시도하거나 drain을 수동 실행한다.
- waiting_input: 상품 상세에서 쿠팡 정보, Ali URL, MP4 또는 파트너스 링크를 입력한다.
- GA4 failed/stale: Property ID, Viewer 권한, Data API 활성화를 확인한 뒤 다시 동기화한다.
- cleanup_pending: Storage 객체 상태를 확인한 뒤 cleanup을 재실행한다.
- Instagram 토큰 만료: Secret Manager에 새 버전을 추가하고 Job을 다시 실행한다.
- 잘못된 배포: Artifact Registry의 이전 SHA 이미지로 Job과 dispatcher 이미지를 되돌린다.
- 비용 제어: Cloud Billing 예산 알림을 켜고 Job task timeout, CPU, memory를 임의로 늘리지 않는다.

실제 게시 E2E는 새 테스트 상품으로만 수행하며 기존 상품 003을 다시 게시하지 않는다.
