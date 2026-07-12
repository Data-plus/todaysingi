const required = ["VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY", "VITE_ADMIN_EMAIL"];
const missing = required.filter((key) => !process.env[key]?.trim());

if (missing.length) {
  console.error(`관리자 배포 중단: Netlify 환경변수 누락 — ${missing.join(", ")}`);
  process.exit(1);
}

if (!process.env.VITE_SUPABASE_URL.startsWith("https://")) {
  console.error("관리자 배포 중단: VITE_SUPABASE_URL은 https:// URL이어야 합니다");
  process.exit(1);
}
