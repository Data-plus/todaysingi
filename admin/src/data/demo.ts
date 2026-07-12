export type Stage = "sourced" | "video_ready" | "script_ready" | "audio_ready" | "caption_ready" | "published" | "linked" | "ads_running" | "analyzed";

export type Product = {
  id: number;
  title: string;
  stage: Stage;
  stageLabel: string;
  updatedAt: string;
  image: string;
  price: string;
  caption: string;
};

export const stages = ["상품", "영상", "대본", "음성", "검수", "게시", "링크", "광고", "분석"];

export const products: Product[] = [
  {
    id: 1,
    title: "불쏘는 마법지팡이",
    stage: "caption_ready",
    stageLabel: "검수 대기",
    updatedAt: "2026.07.12 / 11:24",
    image: "/admin/images/001.jpg",
    price: "12,900원",
    caption: "손끝에서 불꽃이 살아나는 순간. 프로필 링크 [001]번에서 확인하세요.",
  },
];

export const jobs = [
  { id: "JOB-014", name: "Typecast 음성 재생성", product: "OBJECT 001", status: "대기 중", time: "방금 전" },
  { id: "JOB-013", name: "Instagram 캡션 생성", product: "OBJECT 001", status: "완료", time: "12분 전" },
  { id: "JOB-012", name: "세로 영상 합성", product: "OBJECT 001", status: "완료", time: "14분 전" },
];
