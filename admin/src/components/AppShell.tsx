import { useState, type ReactNode } from "react";
import { formatDateTime } from "../lib/dashboard";
import type { AdminView } from "../types/admin";
import { Icon } from "./Icon";

const NAV_ITEMS: Array<{ id: AdminView; label: string; icon: Parameters<typeof Icon>[0]["name"] }> = [
  { id: "overview", label: "개요", icon: "grid" },
  { id: "products", label: "상품", icon: "box" },
  { id: "jobs", label: "작업 큐", icon: "activity" },
  { id: "performance", label: "성과 분석", icon: "chart" },
  { id: "ads", label: "광고", icon: "send" },
  { id: "settings", label: "연동·설정", icon: "settings" },
];

const VIEW_COPY: Record<AdminView, { title: string; description: string }> = {
  overview: { title: "운영 개요", description: "오늘 확인해야 할 상품, 작업, 연결 상태입니다." },
  products: { title: "상품 관리", description: "콘텐츠 단계와 상품별 성과를 함께 관리합니다." },
  jobs: { title: "작업 큐", description: "Cloud Worker에 전달된 자동화 작업을 추적합니다." },
  performance: { title: "성과 분석", description: "클릭부터 주문·수수료까지 데이터 연결을 관리합니다." },
  ads: { title: "광고", description: "A/B 광고안과 비용 대비 성과를 관리할 공간입니다." },
  settings: { title: "연동·설정", description: "외부 서비스와 Worker의 연결 상태를 확인합니다." },
};

export function AppShell({
  view,
  onNavigate,
  search,
  onSearch,
  onNewProduct,
  refreshing,
  onRefresh,
  lastRefresh,
  email,
  live,
  onSignOut,
  children,
}: {
  view: AdminView;
  onNavigate: (view: AdminView) => void;
  search: string;
  onSearch: (value: string) => void;
  onNewProduct: () => void;
  refreshing: boolean;
  onRefresh: () => void;
  lastRefresh: string;
  email: string;
  live: boolean;
  onSignOut: () => void;
  children: ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const copy = VIEW_COPY[view];

  function navigate(nextView: AdminView) {
    onNavigate(nextView);
    setMobileOpen(false);
  }

  return (
    <div className="admin-shell">
      <aside className={`sidebar${mobileOpen ? " sidebar-open" : ""}`} aria-label="관리자 주 메뉴">
        <div className="brand-lockup">
          <span className="brand-mark">TS</span>
          <div><strong>오늘의신기템</strong><small>ADMIN · ISSUE 01</small></div>
        </div>
        <nav className="sidebar-nav">
          <p>운영 메뉴</p>
          {NAV_ITEMS.map((item) => (
            <button
              type="button"
              key={item.id}
              className={view === item.id ? "active" : ""}
              aria-current={view === item.id ? "page" : undefined}
              onClick={() => navigate(item.id)}
            >
              <Icon name={item.icon} size={19}/><span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className={`live-dot${live ? " is-live" : ""}`} aria-hidden="true"/>
          <div><strong>{live ? "운영 데이터 연결됨" : "데모 모드"}</strong><small>{live ? "Supabase · 보호됨" : "환경 변수 미설정"}</small></div>
        </div>
        <div className="sidebar-account">
          <span aria-hidden="true">{email.slice(0, 1).toUpperCase()}</span>
          <div><strong>{email || "관리자"}</strong><small>GitHub 관리자</small></div>
          <button type="button" aria-label="로그아웃" title={live ? "로그아웃" : "데모 모드에서는 사용할 수 없습니다"} onClick={onSignOut} disabled={!live}><Icon name="logout" size={17}/></button>
        </div>
      </aside>

      {mobileOpen ? <button type="button" className="sidebar-scrim" aria-label="메뉴 닫기" onClick={() => setMobileOpen(false)}/> : null}

      <div className="admin-workspace">
        <header className="topbar">
          <button type="button" className="icon-button mobile-menu-button" aria-label="메뉴 열기" onClick={() => setMobileOpen(true)}><Icon name="menu" size={21}/></button>
          <div className="page-heading"><h1>{copy.title}</h1><p>{copy.description}</p></div>
          <div className="topbar-tools">
            <button type="button" className="date-control" disabled title="성과 API 연결 후 기간을 선택할 수 있습니다"><Icon name="calendar" size={16}/>최근 30일</button>
            <label className="global-search">
              <span className="sr-only">전체 상품 검색</span>
              <Icon name="search" size={17}/>
              <input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="상품 검색"/>
            </label>
            <div className="refresh-control">
              <span>최근 조회 {formatDateTime(lastRefresh)}</span>
              <button type="button" className="icon-button" aria-label="데이터 새로고침" title="데이터 새로고침" onClick={onRefresh} disabled={refreshing || !live}>
                <Icon name="refresh" size={18}/>
              </button>
            </div>
            <button type="button" className="primary-button" onClick={onNewProduct} disabled={!live} title={live ? "새 상품 등록" : "Supabase 연결 후 사용할 수 있습니다"}><Icon name="plus" size={17}/>새 상품</button>
          </div>
        </header>
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
