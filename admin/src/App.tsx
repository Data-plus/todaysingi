import { useDeferredValue, useState } from "react";
import { Icon } from "./components/Icon";
import { jobs, products, stages } from "./data/demo";

const nav = [
  ["grid", "대시보드"], ["box", "상품"], ["activity", "작업"],
  ["send", "게시"], ["chart", "광고"], ["settings", "설정"],
] as const;

function App() {
  const [active, setActive] = useState("대시보드");
  const [search, setSearch] = useState("");
  const [modal, setModal] = useState(false);
  const deferredSearch = useDeferredValue(search);
  const visibleProducts = products.filter((p) => p.title.includes(deferredSearch));

  return (
    <div className="app-shell">
      <header className="masthead">
        <a className="brand" href="#top" aria-label="대시보드 홈">
          <span>TODAY'S SINGI</span><em>CONTROL DESK / 2026</em>
        </a>
        <nav className="desktop-nav" aria-label="주 메뉴">
          {nav.map(([icon, label]) => (
            <button className={active === label ? "active" : ""} onClick={() => setActive(label)} key={label}>
              <Icon name={icon} size={17}/>{label}
            </button>
          ))}
        </nav>
        <button className="new-object" onClick={() => setModal(true)}><Icon name="plus" size={17}/>새 상품</button>
      </header>

      <main id="top">
        <section className="hero-grid reveal">
          <div className="issue-mark"><span>ISSUE</span><strong>01</strong><small>SUNDAY<br/>12 JUL 2026</small></div>
          <div className="hero-copy">
            <p className="eyebrow">CONTENT OPERATIONS / SEOUL</p>
            <h1>신기한 물건이<br/><i>콘텐츠가 되는 곳.</i></h1>
            <p className="deck">상품 한 개의 발견부터 영상, 목소리, 게시와 분석까지. 오늘의 흐름을 한눈에 지휘합니다.</p>
          </div>
          <div className="hero-collage" aria-label="현재 작업 상품 이미지">
            <div className="orange-block">OBJECT<br/>OF THE DAY</div>
            <img src={products[0].image} alt="불쏘는 마법지팡이 상품"/>
            <div className="caption-strip">NO. 001 — READY FOR REVIEW</div>
          </div>
        </section>

        <section className="signal-bar" aria-label="운영 현황">
          <div><span>WORKER</span><strong className="offline"><i/>OFFLINE</strong><small>PC를 켜면 작업을 시작합니다</small></div>
          <div><span>QUEUE</span><strong>01</strong><small>대기 중인 작업</small></div>
          <div><span>IN REVIEW</span><strong>01</strong><small>승인이 필요한 콘텐츠</small></div>
          <div><span>PUBLISHED</span><strong>00</strong><small>이번 주 게시물</small></div>
        </section>

        <section className="current-section reveal">
          <div className="section-heading"><p>01 / CURRENT OBJECT</p><h2>지금 다루는 물건</h2><button onClick={() => setActive("상품")}>전체 상품 <Icon name="arrow" size={16}/></button></div>
          {visibleProducts.map((product) => (
            <article className="object-feature" key={product.id}>
              <div className="object-photo"><span>OBJECT {String(product.id).padStart(3,"0")}</span><img src={product.image} alt={product.title}/></div>
              <div className="object-story">
                <div className="stamp">{product.stageLabel}</div>
                <p className="updated">UPDATED {product.updatedAt}</p>
                <h3>{product.title}</h3><p className="price">{product.price}</p>
                <p className="caption">{product.caption}</p>
                <div className="pipeline" aria-label="콘텐츠 제작 단계">
                  {stages.map((stage, index) => <div className={index <= 4 ? "done" : ""} key={stage}><i/><span>{String(index + 1).padStart(2,"0")}</span><b>{stage}</b></div>)}
                </div>
                <div className="actions"><button className="primary"><Icon name="play" size={17}/>영상 검수하기</button><button>상세 보기 <Icon name="arrow" size={16}/></button></div>
              </div>
            </article>
          ))}
        </section>

        <section className="work-section reveal">
          <div className="section-heading"><p>02 / WORK QUEUE</p><h2>작업의 움직임</h2><label className="search"><span>상품 검색</span><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="이름으로 찾기"/></label></div>
          <div className="job-table" role="table" aria-label="최근 작업">
            <div className="job-row head" role="row"><span>작업</span><span>대상</span><span>상태</span><span>시간</span></div>
            {jobs.map((job) => <button className="job-row" role="row" key={job.id}><span><small>{job.id}</small>{job.name}</span><span>{job.product}</span><span><i className={job.status === "완료" ? "ok" : "wait"}/>{job.status}</span><span>{job.time}<Icon name="arrow" size={16}/></span></button>)}
          </div>
        </section>
      </main>

      <nav className="mobile-nav" aria-label="모바일 주 메뉴">
        {nav.slice(0,5).map(([icon,label]) => <button className={active === label ? "active" : ""} onClick={() => setActive(label)} key={label}><Icon name={icon} size={19}/><span>{label}</span></button>)}
      </nav>

      {modal ? <div className="modal-backdrop" onMouseDown={() => setModal(false)}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" onMouseDown={(e) => e.stopPropagation()}><p>NEW ENTRY / 001</p><h2 id="modal-title">새 상품 등록</h2><form onSubmit={(e) => {e.preventDefault(); setModal(false)}}><label htmlFor="title">상품명</label><input id="title" required placeholder="예: 접이식 미니 가습기"/><label htmlFor="url">쿠팡 상품 URL</label><input id="url" required type="url" placeholder="https://..."/><label htmlFor="ali">AliExpress URL <small>선택</small></label><input id="ali" type="url" placeholder="https://..."/><div><button type="button" onClick={() => setModal(false)}>취소</button><button className="primary" type="submit">상품 만들기 <Icon name="arrow" size={16}/></button></div></form></section></div> : null}
    </div>
  );
}

export default App;
