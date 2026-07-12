import { useState } from "react";
import { adminEmail, supabase } from "../lib/supabase";

export function Login() {
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState("");

  async function sendMagicLink() {
    if (!supabase) return;
    setSending(true);
    setMessage("");
    const { error } = await supabase.auth.signInWithOtp({
      email: adminEmail,
      options: { shouldCreateUser: false, emailRedirectTo: window.location.href },
    });
    setMessage(error ? error.message : `${adminEmail}로 로그인 링크를 보냈습니다.`);
    setSending(false);
  }

  return (
    <main className="login-page">
      <section className="login-editorial">
        <p>PRIVATE EDITION / ADMIN ONLY</p>
        <h1>Today's Singi<br/><i>Control Desk.</i></h1>
        <div className="login-rule"/>
        <p className="login-copy">상품의 발견부터 릴스 게시까지, 본인만 접근할 수 있는 운영 관제실입니다.</p>
        <button onClick={sendMagicLink} disabled={sending}>
          {sending ? "보내는 중…" : "이메일로 로그인"}
        </button>
        {message ? <output aria-live="polite">{message}</output> : null}
      </section>
    </main>
  );
}
