import type { Session } from "@supabase/supabase-js";
import { adminEmail } from "./supabase";

const DEFAULT_ADMIN_REDIRECT_URL = "https://todaysingi.netlify.app/admin/";
const configuredRedirectUrl = import.meta.env.VITE_ADMIN_REDIRECT_URL?.trim();

export const adminRedirectUrl = configuredRedirectUrl?.startsWith("https://")
  ? configuredRedirectUrl
  : DEFAULT_ADMIN_REDIRECT_URL;

export function isAuthorizedAdminSession(session: Session): boolean {
  const providerList = session.user.app_metadata.providers;
  const providers = Array.isArray(providerList)
    ? providerList.filter((provider): provider is string => typeof provider === "string")
    : [];
  const primaryProvider = session.user.app_metadata.provider;
  if (typeof primaryProvider === "string") providers.push(primaryProvider);

  return session.user.email?.toLowerCase() === adminEmail
    && providers.includes("github");
}

export function oauthCallbackError(search: string): string {
  const params = new URLSearchParams(search);
  return params.has("error")
    ? "GitHub 로그인을 완료하지 못했습니다. 다시 시도해 주세요."
    : "";
}
