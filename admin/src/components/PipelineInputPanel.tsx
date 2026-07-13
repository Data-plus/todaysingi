import { useEffect, useState } from "react";
import type { AdminJob } from "../types/admin";
import { Icon } from "./Icon";

export function PipelineInputPanel({
  job,
  busy,
  live,
  onSubmitInput,
  onUploadVideo,
}: {
  job?: AdminJob;
  busy: boolean;
  live: boolean;
  onSubmitInput: (jobId: string, input: Record<string, string | number>) => Promise<void>;
  onUploadVideo: (jobId: string, file: File) => Promise<void>;
}) {
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"url" | "file">("url");
  const [productFields, setProductFields] = useState({ title: "", description: "", price: "", imageUrl: "" });
  const waitingFor = typeof job?.result.waiting_for === "string" ? job.result.waiting_for : "";
  const prompt = typeof job?.result.prompt === "string" ? job.result.prompt : "추가 입력이 필요합니다.";

  useEffect(() => {
    setUrl("");
    setFile(null);
    setMode("url");
    setProductFields({ title: "", description: "", price: "", imageUrl: "" });
  }, [job?.id]);

  if (!job) return null;
  const videoInput = waitingFor === "ali_url_or_video";
  const partnersInput = waitingFor === "partners_link";
  const productInput = waitingFor === "coupang_product";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!live || busy) return;
    if (videoInput && mode === "file") {
      if (file) await onUploadVideo(job!.id, file);
      return;
    }
    if (videoInput && url.trim()) await onSubmitInput(job!.id, { ali_url: url.trim() });
    if (partnersInput && url.trim()) await onSubmitInput(job!.id, { partners_link: url.trim() });
    if (productInput && productFields.title.trim()) await onSubmitInput(job!.id, {
      product_title: productFields.title.trim(),
      product_description: productFields.description.trim(),
      ...(productFields.price ? { product_price: Number(productFields.price) } : {}),
      ...(productFields.imageUrl.trim() ? { product_image_url: productFields.imageUrl.trim() } : {}),
    });
  }

  return (
    <section className="drawer-section pipeline-input-panel" aria-labelledby="pipeline-input-title">
      <div className="pipeline-input-heading"><span><Icon name="alert" size={18}/></span><div><p>INPUT REQUIRED</p><h3 id="pipeline-input-title">Cloud 작업에 입력이 필요합니다</h3><small>{prompt}</small></div></div>
      {videoInput ? <div className="input-mode-tabs" role="tablist" aria-label="영상 입력 방법"><button type="button" role="tab" aria-selected={mode === "url"} onClick={() => setMode("url")}>AliExpress URL</button><button type="button" role="tab" aria-selected={mode === "file"} onClick={() => setMode("file")}>MP4 직접 업로드</button></div> : null}
      <form onSubmit={(event) => void submit(event)}>
        {videoInput && mode === "file" ? <label className="manual-file-input"><span>원본 MP4 · 최대 오백 MB</span><input type="file" accept="video/mp4,.mp4" required onChange={(event) => setFile(event.target.files?.[0] || null)}/><strong>{file?.name || "파일 선택"}</strong></label> : null}
        {videoInput && mode === "url" ? <label><span>AliExpress 상품 URL</span><input type="url" required value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://www.aliexpress.com/item/..."/></label> : null}
        {partnersInput ? <label><span>쿠팡 파트너스 링크</span><input type="url" required value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://link.coupang.com/a/..."/></label> : null}
        {productInput ? <div className="manual-product-fields"><label><span>상품명</span><input required value={productFields.title} onChange={(event) => setProductFields({ ...productFields, title: event.target.value })}/></label><label><span>가격</span><input type="number" min="0" step="1" value={productFields.price} onChange={(event) => setProductFields({ ...productFields, price: event.target.value })}/></label><label className="field-wide"><span>이미지 URL</span><input type="url" value={productFields.imageUrl} onChange={(event) => setProductFields({ ...productFields, imageUrl: event.target.value })} placeholder="https://..."/></label><label className="field-wide"><span>상품 설명</span><textarea rows={3} value={productFields.description} onChange={(event) => setProductFields({ ...productFields, description: event.target.value })}/></label></div> : null}
        {!videoInput && !partnersInput && !productInput ? <p className="pipeline-input-unsupported">연동 설정을 확인한 뒤 작업을 다시 요청하세요.</p> : null}
        {videoInput || partnersInput || productInput ? <button type="submit" className="primary-button" disabled={!live || busy || (videoInput && mode === "file" ? !file : videoInput || partnersInput ? !url.trim() : !productFields.title.trim())}>{busy ? "전송 중…" : "입력하고 작업 재개"}<Icon name="arrow" size={16}/></button> : null}
      </form>
    </section>
  );
}
