// 오른쪽 "상담 결과" 패널: 위험도, 대응 권고, 근거 조문, 증거 자료(첨부), 안내 문구, PDF 인쇄.
import type { HTMLAttributes, RefObject } from "react";

import { attachmentDownloadUrl } from "../../api";
import type { Assessment, Attachment } from "../../types";
import CitationCards from "./CitationCards";
import { DEFAULT_ASIDE_WIDTH, riskLabel } from "../constants";
import { formatBytes } from "../format";

interface Props {
  assessment: Assessment;
  attachments: Attachment[];
  uploading: boolean;
  asideWidth: number;
  /** 왼쪽 가장자리의 너비 조절 구분선에 펼칠 속성 (usePanelResize) */
  resizerProps: HTMLAttributes<HTMLDivElement>;
  fileInput: RefObject<HTMLInputElement | null>;
  onResetWidth: (width: number) => void;
  onClose: () => void;
  onDeleteAttachment: (attachmentId: number) => void;
  onPrint: () => void;
}

export default function ResultPanel({
  assessment, attachments, uploading, asideWidth, resizerProps, fileInput,
  onResetWidth, onClose, onDeleteAttachment, onPrint,
}: Props) {
  return (
    <aside className={`aside ${asideWidth <= 48 ? "aside-minimized" : ""}`}>
      {asideWidth <= 48 && (
        <button
          type="button"
          className="aside-restore-btn"
          onClick={() => onResetWidth(DEFAULT_ASIDE_WIDTH)}
          aria-label="상담 결과창 기본 너비로 복원"
          title="기본 너비로 복원"
        >
          ‹
        </button>
      )}
      <div className="aside-resizer" {...resizerProps} />

      <div className="aside-head">
        <div>
          <h2>상담 결과</h2>
          <small>입력 내용 기반 임시 분석</small>
        </div>
        <button onClick={onClose}>›</button>
      </div>

      <div className="aside-scroll">
        <div className="meta"><span>분류</span><b>{assessment.category}</b></div>

        <section className={`risk ${assessment.level}`}>
          <label>위험도</label>
          <div className="risk-card">
            <div>
              <strong>{riskLabel[assessment.level]}</strong>
              <b>{assessment.score} / 100</b>
            </div>
            <div className="gauge"><i style={{ width: `${assessment.score}%` }} /></div>
            <p>{assessment.rationale}</p>
          </div>
        </section>

        <section className="result">
          <label>대응 권고</label>
          <div>
            {assessment.actions.length ? (
              <ol>{assessment.actions.map(x => <li key={x}>{x}</li>)}</ol>
            ) : (
              <p>상담을 진행하면 단계별 조치가 표시됩니다.</p>
            )}
          </div>
        </section>

        <CitationCards citations={assessment.citations ?? []} />

        <section className="attachments">
          <label>증거 자료</label>
          <div>
            <button
              type="button"
              className="upload-btn"
              disabled={uploading}
              onClick={() => fileInput.current?.click()}
            >
              {uploading ? "업로드 중…" : "📎 파일 첨부"}
            </button>

            {attachments.length > 0 && (
              <ul className="file-list">
                {attachments.map(attachment => (
                  <li key={attachment.id}>
                    <a
                      href={attachmentDownloadUrl(attachment.case_id, attachment.id)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {attachment.filename}
                    </a>
                    <small>{formatBytes(attachment.size)}</small>
                    <button type="button" onClick={() => onDeleteAttachment(attachment.id)}>✕</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="notice">
          <b>꼭 확인하세요</b>
          <p>법령과 절차는 개정될 수 있습니다. 이 앱의 결과만으로 신고·징계·법적 조치를 결정하지 마세요.</p>
        </section>
      </div>

      <div className="aside-actions"><button onClick={onPrint}>PDF로 인쇄</button></div>
    </aside>
  );
}
