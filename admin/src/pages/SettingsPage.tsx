import { Icon } from "../components/Icon";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../lib/dashboard";
import type { AdminWorker, ConnectionInfo } from "../types/admin";

export function SettingsPage({ connections, workers }: { connections: ConnectionInfo[]; workers: AdminWorker[] }) {
  return (
    <div className="page-stack">
      <section className="settings-intro"><div><p className="section-kicker">CONNECTIONS</p><h2>서비스 연결 상태</h2><p>비밀키 값은 이 화면과 브라우저에 표시하거나 저장하지 않습니다.</p></div><span className="security-label"><Icon name="check" size={15}/>관리자 RLS 보호</span></section>
      <section className="connections-grid">
        {connections.map((connection) => <article className="connection-card" key={connection.id}><div className="connection-card-heading"><span className="connection-symbol">{connection.id.slice(0, 2).toUpperCase()}</span><div><h2>{connection.name}</h2><p>{connection.detail}</p></div></div><div className="connection-card-footer"><StatusBadge status={connection.status} label={connection.label}/><button type="button" className="text-button" disabled title="환경 변수와 권한은 서버 또는 Worker에서 관리합니다">서버에서 관리</button></div></article>)}
      </section>

      <section className="section-block">
        <div className="section-title-row compact"><div><p className="section-kicker">LOCAL WORKERS</p><h2>영상 처리 PC</h2><p>PC를 필요할 때 켜면 대기 작업을 이어서 처리합니다.</p></div></div>
        <div className="table-card"><table className="data-table workers-table"><thead><tr><th>Worker</th><th>상태</th><th>현재 작업</th><th>버전</th><th>마지막 신호</th></tr></thead><tbody>{workers.length ? workers.map((worker) => <tr key={worker.id}><td data-label="Worker"><span className="worker-name"><Icon name="cpu" size={18}/><span><strong>{worker.name}</strong><small>{worker.id}</small></span></span></td><td data-label="상태"><StatusBadge status={worker.online ? "online" : "offline"} label={worker.statusLabel}/></td><td data-label="현재 작업">{worker.currentJobId ? worker.currentJobId.slice(0, 8) : "—"}</td><td data-label="버전">{worker.version || "미기록"}</td><td data-label="마지막 신호">{formatDateTime(worker.lastSeenAt)}</td></tr>) : <tr><td colSpan={5}><div className="empty-state"><Icon name="cpu" size={25}/><strong>등록된 Worker가 없습니다.</strong><p>로컬 PC에서 Worker를 실행하면 자동으로 표시됩니다.</p></div></td></tr>}</tbody></table></div>
      </section>

      <section className="settings-guidance"><h2>다음 연결 순서</h2><ol><li><span>01</span><div><strong>쿠팡 파트너스 최종 승인</strong><p>승인 후 Access Key와 Secret Key를 서버 측 수집기에 등록합니다.</p></div></li><li><span>02</span><div><strong>GA4 Data API 자격 증명</strong><p>Property ID와 최소 권한 서비스 계정을 연결합니다.</p></div></li><li><span>03</span><div><strong>Meta 광고 지표 저장소</strong><p>광고 계정 권한을 검증하고 일별 Insights를 저장합니다.</p></div></li></ol></section>
    </div>
  );
}
