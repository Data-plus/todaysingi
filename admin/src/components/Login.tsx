import { useState } from "react";
import { Icon } from "./Icon";
import { adminRedirectUrl, oauthCallbackError } from "../lib/auth";
import { supabase } from "../lib/supabase";

export function Login() {
  const [signingIn, setSigningIn] = useState(false);
  const [message, setMessage] = useState(() => oauthCallbackError(window.location.search));

  async function signInWithGitHub() {
    if (!supabase) return;
    setSigningIn(true);
    setMessage("");
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "github",
      options: { redirectTo: adminRedirectUrl },
    });
    if (error) {
      setMessage(`GitHub 로그인을 시작하지 못했습니다: ${error.message}`);
      setSigningIn(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-editorial">
        <p>PRIVATE EDITION / ADMIN ONLY</p>
        <h1>Today's Singi<br/><i>Control Desk.</i></h1>
        <div className="login-rule"/>
        <p className="login-copy">상품의 발견부터 릴스 게시까지, 본인만 접근할 수 있는 운영 관제실입니다.</p>
        <button onClick={signInWithGitHub} disabled={signingIn}>
          <Icon name="github" size={18}/>
          {signingIn ? "GitHub로 이동 중…" : "GitHub로 계속하기"}
        </button>
        <p className="login-note">승인된 GitHub 계정 한 개만 입장할 수 있습니다.</p>
        {message ? <output aria-live="polite">{message}</output> : null}
      </section>
    </main>
  );
}
