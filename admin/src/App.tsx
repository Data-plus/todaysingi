import type { Session } from "@supabase/supabase-js";
import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import { Icon } from "./components/Icon";
import { Login } from "./components/Login";
import { jobs as demoJobs, products as demoProducts, stages } from "./data/demo";
import type { Product } from "./data/demo";
import { createProduct, enqueueDub, loadDeskData } from "./lib/controlDesk";
import type { DeskData, DeskJob } from "./lib/controlDesk";
import { isAuthorizedAdminSession } from "./lib/auth";
import { isSupabaseConfigured, supabase } from "./lib/supabase";

const nav = [
  ["grid", "대시보드"], ["box", "상품"], ["activity", "작업"],
  ["send", "게시"], ["chart", "광고"], ["settings", "설정"],
] as const;
const stageSlugs = ["sourced", "video_ready", "script_ready", "audio_ready", "caption_ready", "published", "linked", "ads_running", "analyzed"];
const demoDesk: DeskData = {
  products: demoProducts,
  jobs: demoJobs,
  worker: { online: false, label: "OFFLINE", detail: "PC를 켜면 작업을 시작합니다" },
  queueCount: 1, reviewCount: 1, publishedCount: 0,
};

function useSession() {
  const [session, setSession] = useState<Session | null | undefined>(isSupabaseConfigured ? undefined : null);
  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, []);
  return session;
}

function Dashboard({ live }: { live: boolean }) {
  const [active, setActive] = useState("대시보드");
  const [search, setSearch] = useState("");
  const [modal, setModal] = useState(false);
  const [desk, setDesk] = useState<DeskData>(demoDesk);
  const [busyProduct, setBusyProduct] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ title: "", coupangUrl: "", aliUrl: "" });
  const deferredSearch = useDeferredValue(search);

  const refresh = useCallback(async () => {
    if (!live) return;
    try {
      setDesk(await loadDeskData());
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "데이터를 불러오지 못했습니다");
    }
  }, [live]);

  useEffect(() => {
    void refresh();
    if (!live) return;
    const timer = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(timer);
  }, [live, refresh]);

  const visibleProducts = useMemo(
    () => desk.products.filter((product) => product.title.includes(deferredSearch)),
    [desk.products, deferredSearch],
  );
  const current = visibleProducts[0] || desk.products[0];

  async function requestDub(product: Product) {
    if (!live) return;
    setBusyProduct(product.id);
    try {
      await enqueueDub(product.id);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "작업 요청에 실패했습니다");
    } finally {
      setBusyProduct(null);
    }
  }

  async function submitProduct(event: React.FormEvent) {
    event.preventDefault();
    if (!live) { setModal(false); return; }
    try {
      await createProduct(form);
      setForm({ title: "", coupangUrl: "", aliUrl: "" });
      setModal(false);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "상품 등록에 실패했습니다");
    }
  }

  return (
    <div className="app-shell">
      <header className="masthead">
        <a className="brand" href="#top" aria-label="대시보드 홈"><span>TODAY'S SINGI</span><em>CONTROL DESK / 2026</em></a>
        <nav className="desktop-nav" aria-label="주 메뉴">{nav.map(([icon, label]) => <button className={active === label ? "active" : ""} onClick={() => setActive(label)} key={label}><Icon name={icon} size={17}/>{label}</button>)}</nav>
        <button className="new-object" onClick={() => setModal(true)}><Icon name="plus" size={17}/>새 상품</button>
      </header>
      {!live ? <div className="mode-banner">DEMO MODE · Supabase 연결 전 미리보기</div> : null}
      {error ? <div className="error-banner" role="alert">{error}<button onClick={() => setError("")}>닫기</button></div> : null}

      <main id="top">
        <section className="hero-grid reveal">
          <div className="issue-mark"><span>ISSUE</span><strong>{String(desk.products.length).padStart(2, "0")}</strong><small>SUNDAY<br/>12 JUL 2026</small></div>
          <div className="hero-copy"><p className="eyebrow">CONTENT OPERATIONS / SEOUL</p><h1>신기한 물건이<br/><i>콘텐츠가 되는 곳.</i></h1><p className="deck">상품 한 개의 발견부터 영상, 목소리, 게시와 분석까지. 오늘의 흐름을 한눈에 지휘합니다.</p></div>
          <div className="hero-collage" aria-label="현재 작업 상품 이미지"><div className="orange-block">OBJECT<br/>OF THE DAY</div>{current ? <img src={current.image} alt={`${current.title} 상품`} onError={(e) => { e.currentTarget.style.visibility = "hidden"; }}/> : null}<div className="caption-strip">{current ? `NO. ${String(current.id).padStart(3, "0")} — ${current.stageLabel}` : "NO ACTIVE OBJECT"}</div></div>
        </section>

        <section className="signal-bar" aria-label="운영 현황">
          <div><span>WORKER</span><strong className={desk.worker.online ? "online" : "offline"}><i/>{desk.worker.label}</strong><small>{desk.worker.detail}</small></div>
          <div><span>QUEUE</span><strong>{String(desk.queueCount).padStart(2, "0")}</strong><small>대기 중인 작업</small></div>
          <div><span>IN REVIEW</span><strong>{String(desk.reviewCount).padStart(2, "0")}</strong><small>승인이 필요한 콘텐츠</small></div>
          <div><span>PUBLISHED</span><strong>{String(desk.publishedCount).padStart(2, "0")}</strong><small>게시 완료 상품</small></div>
        </section>

        <section className="current-section reveal">
          <div className="section-heading"><p>01 / CURRENT OBJECT</p><h2>지금 다루는 물건</h2><button onClick={() => setActive("상품")}>전체 상품 <Icon name="arrow" size={16}/></button></div>
          {current ? <ProductFeature product={current} busy={busyProduct === current.id} onDub={() => void requestDub(current)}/> : <p className="empty-desk">등록된 상품이 없습니다. 첫 상품을 추가하세요.</p>}
        </section>

        <section className="work-section reveal">
          <div className="section-heading"><p>02 / WORK QUEUE</p><h2>작업의 움직임</h2><label className="search"><span>상품 검색</span><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="이름으로 찾기"/></label></div>
          <JobTable jobs={desk.jobs}/>
        </section>
      </main>

      <nav className="mobile-nav" aria-label="모바일 주 메뉴">{nav.slice(0,5).map(([icon,label]) => <button className={active === label ? "active" : ""} onClick={() => setActive(label)} key={label}><Icon name={icon} size={19}/><span>{label}</span></button>)}</nav>
      {modal ? <div className="modal-backdrop" onMouseDown={() => setModal(false)}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" onMouseDown={(e) => e.stopPropagation()}><p>NEW ENTRY</p><h2 id="modal-title">새 상품 등록</h2><form onSubmit={submitProduct}><label htmlFor="title">상품명</label><input id="title" required value={form.title} onChange={(e) => setForm({...form, title:e.target.value})} placeholder="예: 접이식 미니 가습기"/><label htmlFor="url">쿠팡 상품 URL</label><input id="url" required type="url" value={form.coupangUrl} onChange={(e) => setForm({...form, coupangUrl:e.target.value})} placeholder="https://..."/><label htmlFor="ali">AliExpress URL <small>선택</small></label><input id="ali" type="url" value={form.aliUrl} onChange={(e) => setForm({...form, aliUrl:e.target.value})} placeholder="https://..."/><div><button type="button" onClick={() => setModal(false)}>취소</button><button className="primary" type="submit">상품 만들기 <Icon name="arrow" size={16}/></button></div></form></section></div> : null}
    </div>
  );
}

function ProductFeature({ product, busy, onDub }: { product: Product; busy: boolean; onDub: () => void }) {
  const reached = Math.max(0, stageSlugs.indexOf(product.stage));
  return <article className="object-feature"><div className="object-photo"><span>OBJECT {String(product.id).padStart(3,"0")}</span><img src={product.image} alt={product.title} onError={(e) => { e.currentTarget.style.visibility = "hidden"; }}/></div><div className="object-story"><div className="stamp">{product.stageLabel}</div><p className="updated">UPDATED {product.updatedAt}</p><h3>{product.title}</h3><p className="price">{product.price}</p><p className="caption">{product.caption}</p><div className="pipeline" aria-label="콘텐츠 제작 단계">{stages.map((stage,index) => <div className={index <= reached ? "done" : ""} key={stage}><i/><span>{String(index+1).padStart(2,"0")}</span><b>{stage}</b></div>)}</div><div className="actions"><button className="primary"><Icon name="play" size={17}/>영상 검수하기</button><button onClick={onDub} disabled={busy}>{busy ? "요청 중…" : "Typecast 재더빙"}<Icon name="arrow" size={16}/></button></div></div></article>;
}

function JobTable({ jobs }: { jobs: DeskJob[] }) {
  return <div className="job-table" role="table" aria-label="최근 작업"><div className="job-row head" role="row"><span>작업</span><span>대상</span><span>상태</span><span>시간</span></div>{jobs.length ? jobs.map((job) => <button className="job-row" role="row" key={job.id}><span><small>{job.id}</small>{job.name}</span><span>{job.product}</span><span><i className={job.status === "완료" ? "ok" : job.status === "실패" ? "fail" : "wait"}/>{job.status}</span><span>{job.time}<Icon name="arrow" size={16}/></span></button>) : <p className="empty-desk">아직 작업 기록이 없습니다.</p>}</div>;
}

function App() {
  const session = useSession();
  if (!isSupabaseConfigured) return <Dashboard live={false}/>;
  if (session === undefined) return <div className="loading-page">CONTROL DESK 불러오는 중…</div>;
  if (!session) return <Login/>;
  if (!isAuthorizedAdminSession(session)) return <main className="login-page"><section className="login-editorial"><p>ACCESS DENIED</p><h1>허용되지 않은<br/>GitHub 계정입니다.</h1><button onClick={() => void supabase?.auth.signOut()}>로그아웃</button></section></main>;
  return <Dashboard live/>;
}

export default App;
