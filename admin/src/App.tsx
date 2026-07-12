import type { Session } from "@supabase/supabase-js";
import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import { AppShell } from "./components/AppShell";
import { Icon } from "./components/Icon";
import { Login } from "./components/Login";
import { ProductDrawer } from "./components/ProductDrawer";
import { isAuthorizedAdminSession } from "./lib/auth";
import {
  cancelJob,
  createProduct,
  enqueueDub,
  enqueueGenerateCover,
  enqueuePipelineSync,
  loadDeskData,
  retryJob,
} from "./lib/controlDesk";
import { buildConnections, EMPTY_EXTERNAL_METRICS, JOB_LABELS, JOB_STATUS_LABELS, STAGE_LABELS } from "./lib/dashboard";
import { isSupabaseConfigured, supabase } from "./lib/supabase";
import { AdsPage } from "./pages/AdsPage";
import { JobsPage } from "./pages/JobsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { PerformancePage } from "./pages/PerformancePage";
import { ProductsPage } from "./pages/ProductsPage";
import { SettingsPage } from "./pages/SettingsPage";
import type { AdminJob, AdminView, DeskData } from "./types/admin";
import type { CoverGenerateInput } from "./components/CoverEditor";

const VALID_VIEWS = new Set<AdminView>(["overview", "products", "jobs", "performance", "ads", "settings"]);

const DEMO_DATA: DeskData = {
  products: [{
    id: 1,
    title: "불쏘는 마법지팡이",
    stage: "linked",
    stageLabel: STAGE_LABELS.linked,
    price: 28_500,
    imageUrl: "/admin/images/001.jpg",
    coupangUrl: "https://www.coupang.com/",
    aliUrl: null,
    partnersLink: "https://link.coupang.com/",
    reelUrl: "https://www.instagram.com/reel/DarULTkCZk5/",
    instagramMediaId: null,
    siteProductId: "001",
    note: "데모 모드에서는 조회만 가능합니다.",
    active: true,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    metrics: { ...EMPTY_EXTERNAL_METRICS },
  }],
  jobs: [{
    id: "demo-job-001",
    displayId: "JOB-DEMO01",
    type: "sync_pipeline",
    typeLabel: JOB_LABELS.sync_pipeline,
    status: "succeeded",
    statusLabel: JOB_STATUS_LABELS.succeeded,
    productId: 1,
    productTitle: "불쏘는 마법지팡이",
    payload: {},
    result: {},
    priority: 100,
    progress: 100,
    attempts: 1,
    maxAttempts: 3,
    claimedBy: null,
    errorSummary: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }],
  workers: [],
  assets: [],
  worker: { online: false, label: "오프라인", detail: "PC를 켜면 작업을 시작합니다", version: null },
  loadedAt: new Date().toISOString(),
};

function viewFromHash(): AdminView {
  const hash = window.location.hash.replace(/^#\/?/, "") as AdminView;
  return VALID_VIEWS.has(hash) ? hash : "overview";
}

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

function NewProductDialog({ open, live, submitting, onClose, onSubmit }: { open: boolean; live: boolean; submitting: boolean; onClose: () => void; onSubmit: (input: { title: string; coupangUrl: string; aliUrl?: string }) => void }) {
  const [form, setForm] = useState({ title: "", coupangUrl: "", aliUrl: "" });
  if (!open) return null;

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!live) return;
    onSubmit(form);
  }

  return (
    <div className="dialog-backdrop" onMouseDown={onClose}>
      <section className="form-dialog" role="dialog" aria-modal="true" aria-labelledby="new-product-title" onMouseDown={(event) => event.stopPropagation()}>
        <header><div><p>NEW PRODUCT</p><h2 id="new-product-title">새 상품 등록</h2><span>쿠팡 상품을 먼저 등록하고 로컬 파이프라인을 시작합니다.</span></div><button type="button" className="icon-button" aria-label="새 상품 창 닫기" onClick={onClose}><Icon name="close" size={20}/></button></header>
        {!live ? <p className="dialog-warning"><Icon name="alert" size={16}/>Supabase 연결 후 상품을 등록할 수 있습니다.</p> : null}
        <form onSubmit={submit}>
          <label htmlFor="product-title">상품명</label>
          <input id="product-title" required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="예: 접이식 미니 가습기"/>
          <label htmlFor="coupang-url">쿠팡 상품 URL</label>
          <input id="coupang-url" required type="url" value={form.coupangUrl} onChange={(event) => setForm({ ...form, coupangUrl: event.target.value })} placeholder="https://www.coupang.com/..."/>
          <label htmlFor="ali-url">AliExpress URL <span>선택</span></label>
          <input id="ali-url" type="url" value={form.aliUrl} onChange={(event) => setForm({ ...form, aliUrl: event.target.value })} placeholder="https://www.aliexpress.com/..."/>
          <footer><button type="button" className="secondary-button" onClick={onClose}>취소</button><button type="submit" className="primary-button" disabled={!live || submitting}>{submitting ? "등록 중…" : "상품 등록"}<Icon name="arrow" size={16}/></button></footer>
        </form>
      </section>
    </div>
  );
}

function Dashboard({ live, email }: { live: boolean; email: string }) {
  const [view, setView] = useState<AdminView>(viewFromHash);
  const [search, setSearch] = useState("");
  const [data, setData] = useState<DeskData | null>(() => live ? null : DEMO_DATA);
  const [newProductOpen, setNewProductOpen] = useState(false);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [busyProductId, setBusyProductId] = useState<number | null>(null);
  const [busyCoverProductId, setBusyCoverProductId] = useState<number | null>(null);
  const [busyJobId, setBusyJobId] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [submittingProduct, setSubmittingProduct] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const deferredSearch = useDeferredValue(search.trim().toLocaleLowerCase("ko-KR"));

  const refresh = useCallback(async () => {
    if (!live) return;
    setRefreshing(true);
    try {
      setData(await loadDeskData());
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "관리자 데이터를 불러오지 못했습니다");
    } finally {
      setRefreshing(false);
    }
  }, [live]);

  useEffect(() => {
    void refresh();
    if (!live) return;
    const timer = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(timer);
  }, [live, refresh]);

  useEffect(() => {
    function handleHashChange() {
      setView(viewFromHash());
    }
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  function navigate(nextView: AdminView) {
    setView(nextView);
    if (window.location.hash !== `#${nextView}`) window.location.hash = nextView;
  }

  const visibleProducts = useMemo(() => {
    if (!data || !deferredSearch) return data?.products || [];
    return data.products.filter((product) => product.title.toLocaleLowerCase("ko-KR").includes(deferredSearch) || String(product.id).includes(deferredSearch));
  }, [data, deferredSearch]);
  const visibleJobs = useMemo(() => {
    if (!data || !deferredSearch) return data?.jobs || [];
    return data.jobs.filter((job) => job.productTitle.toLocaleLowerCase("ko-KR").includes(deferredSearch) || job.typeLabel.toLocaleLowerCase("ko-KR").includes(deferredSearch) || job.displayId.toLocaleLowerCase().includes(deferredSearch));
  }, [data, deferredSearch]);
  const selectedProduct = data?.products.find((product) => product.id === selectedProductId) || null;
  const selectedJobs = selectedProduct ? data?.jobs.filter((job) => job.productId === selectedProduct.id) || [] : [];
  const selectedAssets = selectedProduct ? data?.assets.filter((asset) => asset.productId === selectedProduct.id) || [] : [];
  const connections = useMemo(() => data ? buildConnections(data, live) : [], [data, live]);

  async function requestDub(productId: number) {
    if (!live) return;
    setBusyProductId(productId);
    try {
      await enqueueDub(productId);
      setNotice("Typecast 재더빙 작업을 대기열에 추가했습니다.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "더빙 작업 요청에 실패했습니다");
    } finally {
      setBusyProductId(null);
    }
  }

  async function requestCover(productId: number, input: CoverGenerateInput) {
    if (!live) return;
    setBusyCoverProductId(productId);
    try {
      await enqueueGenerateCover(productId, input);
      setNotice("릴스 커버 생성 작업을 대기열에 추가했습니다.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "커버 생성 요청에 실패했습니다");
    } finally {
      setBusyCoverProductId(null);
    }
  }

  async function handleJobAction(job: AdminJob, action: "cancel" | "retry") {
    if (!live) return;
    setBusyJobId(job.id);
    try {
      if (action === "cancel") await cancelJob(job);
      else await retryJob(job);
      setNotice(action === "cancel" ? "작업을 취소했습니다." : "새 작업으로 다시 요청했습니다.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "작업 상태를 변경하지 못했습니다");
    } finally {
      setBusyJobId(null);
    }
  }

  async function handleSync() {
    if (!live) return;
    setSyncing(true);
    try {
      await enqueuePipelineSync();
      setNotice("파이프라인 동기화를 요청했습니다.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "동기화 요청에 실패했습니다");
    } finally {
      setSyncing(false);
    }
  }

  async function submitProduct(input: { title: string; coupangUrl: string; aliUrl?: string }) {
    setSubmittingProduct(true);
    try {
      await createProduct(input);
      setNewProductOpen(false);
      setNotice("새 상품과 로컬 생성 작업을 등록했습니다.");
      await refresh();
      navigate("products");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "상품을 등록하지 못했습니다");
    } finally {
      setSubmittingProduct(false);
    }
  }

  if (!data) return <div className="loading-page"><span className="loading-spinner" aria-hidden="true"/><strong>운영 데이터를 불러오는 중입니다.</strong></div>;

  let page: React.ReactNode;
  if (view === "products") page = <ProductsPage products={data.products} search={deferredSearch} onSelectProduct={(product) => setSelectedProductId(product.id)}/>;
  else if (view === "jobs") page = <JobsPage jobs={visibleJobs} busyJobId={busyJobId} syncing={syncing} live={live} onCancel={(job) => void handleJobAction(job, "cancel")} onRetry={(job) => void handleJobAction(job, "retry")} onSync={() => void handleSync()}/>;
  else if (view === "performance") page = <PerformancePage products={visibleProducts} connections={connections} onOpenSettings={() => navigate("settings")}/>;
  else if (view === "ads") page = <AdsPage connections={connections} onOpenSettings={() => navigate("settings")}/>;
  else if (view === "settings") page = <SettingsPage connections={connections} workers={data.workers}/>;
  else page = <OverviewPage data={data} products={visibleProducts} onNavigate={navigate} onSelectProduct={(product) => setSelectedProductId(product.id)}/>;

  return (
    <AppShell
      view={view}
      onNavigate={navigate}
      search={search}
      onSearch={setSearch}
      onNewProduct={() => setNewProductOpen(true)}
      refreshing={refreshing}
      onRefresh={() => void refresh()}
      lastRefresh={data.loadedAt}
      email={email}
      live={live}
      onSignOut={() => void supabase?.auth.signOut()}
    >
      {!live ? <div className="mode-banner" role="status"><Icon name="alert" size={15}/>데모 모드 · Supabase 연결 전 미리보기</div> : null}
      {error ? <div className="app-message message-error" role="alert"><Icon name="alert" size={17}/><span>{error}</span><button type="button" aria-label="오류 닫기" onClick={() => setError("")}><Icon name="close" size={16}/></button></div> : null}
      {notice ? <div className="app-message message-success" role="status"><Icon name="check" size={17}/><span>{notice}</span><button type="button" aria-label="알림 닫기" onClick={() => setNotice("")}><Icon name="close" size={16}/></button></div> : null}
      {page}
      <NewProductDialog open={newProductOpen} live={live} submitting={submittingProduct} onClose={() => setNewProductOpen(false)} onSubmit={(input) => void submitProduct(input)}/>
      {selectedProduct ? <ProductDrawer product={selectedProduct} jobs={selectedJobs} assets={selectedAssets} busy={busyProductId === selectedProduct.id} coverBusy={busyCoverProductId === selectedProduct.id} workerOnline={data.worker.online} live={live} onClose={() => setSelectedProductId(null)} onDub={() => void requestDub(selectedProduct.id)} onGenerateCover={(input) => void requestCover(selectedProduct.id, input)}/> : null}
    </AppShell>
  );
}

function App() {
  const session = useSession();
  if (!isSupabaseConfigured) return <Dashboard live={false} email="demo@todaysingi.local"/>;
  if (session === undefined) return <div className="loading-page"><span className="loading-spinner" aria-hidden="true"/><strong>관리자 인증을 확인하는 중입니다.</strong></div>;
  if (!session) return <Login/>;
  if (!isAuthorizedAdminSession(session)) return <main className="login-page"><section className="login-editorial"><p>ACCESS DENIED</p><h1>허용되지 않은 GitHub 계정입니다.</h1><p className="login-copy">등록된 관리자 계정으로 다시 로그인하세요.</p><button onClick={() => void supabase?.auth.signOut()}>로그아웃</button></section></main>;
  return <Dashboard live email={session.user.email || "plusmg@gmail.com"}/>;
}

export default App;
