import type { AdminJob, ProductStage } from "../types/admin";

export type PublishButtonKind = "ready" | "busy" | "blocked" | "queued" | "running" | "published";

export type PublishButtonState = {
  kind: PublishButtonKind;
  disabled: boolean;
  label: string;
  hint: string;
};

type PublishStateInput = {
  stage: ProductStage;
  reelUrl: string | null;
  jobs: Array<Pick<AdminJob, "type" | "status">>;
  workerOnline: boolean;
  busy: boolean;
};

const PUBLISHED_STAGES = new Set<ProductStage>([
  "published",
  "linked",
  "ads_running",
  "analyzed",
]);

export function getPublishButtonState({ stage, reelUrl, jobs, workerOnline, busy }: PublishStateInput): PublishButtonState {
  if (busy) {
    return {
      kind: "busy",
      disabled: true,
      label: "승인 처리 중…",
      hint: "게시 승인 작업을 안전하게 생성하고 있습니다.",
    };
  }

  if (reelUrl || PUBLISHED_STAGES.has(stage)) {
    return {
      kind: "published",
      disabled: true,
      label: "게시 완료",
      hint: "이미 Instagram에 게시된 상품입니다.",
    };
  }

  const activePublish = jobs.find((job) => (
    job.type === "publish_reel"
    && (job.status === "queued" || job.status === "claimed" || job.status === "running")
  ));

  if (activePublish?.status === "claimed" || activePublish?.status === "running") {
    return {
      kind: "running",
      disabled: true,
      label: "게시 중",
      hint: "Worker가 Instagram 게시 작업을 처리하고 있습니다.",
    };
  }

  if (activePublish?.status === "queued") {
    return {
      kind: "queued",
      disabled: true,
      label: workerOnline ? "게시 대기" : "게시 대기 · Worker를 켜면 처리",
      hint: workerOnline
        ? "승인된 게시 작업이 Worker의 처리를 기다리고 있습니다."
        : "승인된 작업은 대기열에 보관됩니다. PC에서 Worker를 켜면 처리됩니다.",
    };
  }

  if (stage !== "caption_ready") {
    return {
      kind: "blocked",
      disabled: true,
      label: "캡션 완성 후 게시 가능",
      hint: "영상, 음성, 자막과 캡션 준비를 먼저 완료하세요.",
    };
  }

  return {
    kind: "ready",
    disabled: false,
    label: "릴스 게시 승인",
    hint: workerOnline
      ? "승인하면 Worker가 Instagram 게시를 시작합니다."
      : "승인하면 대기열에 저장됩니다. PC에서 Worker를 켜면 자동 게시됩니다.",
  };
}
