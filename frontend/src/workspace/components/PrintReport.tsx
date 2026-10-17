// 인쇄(PDF 저장)용 사건 보고서. 화면에서는 숨겨져 있고, 인쇄할 때만 보인다(@media print).
import type { Assessment, Attachment, CaseItem, Message } from "../../types";
import { riskLabel } from "../constants";
import { formatBytes, formatDate } from "../format";

interface Props {
  active: CaseItem;
  assessment: Assessment;
  messages: Message[];
  attachments: Attachment[];
}

export default function PrintReport({ active, assessment, messages, attachments }: Props) {
  return (
    <section className="report-print">
      <header className="report-head">
        <h1>교권 침해 상담 사건 보고서</h1>
        <p>Case Report for Teacher-Rights Infringement Consultation</p>
      </header>
      <table className="report-meta">
        <tbody>
          <tr>
            <th>사건 번호</th><td>#{String(active.id).padStart(4, "0")}</td>
            <th>작성일</th><td>{formatDate(active.created_at)}</td>
          </tr>
          <tr>
            <th>상담 제목</th><td>{active.title}</td>
            <th>최종 수정일</th><td>{formatDate(active.updated_at)}</td>
          </tr>
          <tr>
            <th>사건 분류</th><td>{assessment.category}</td>
            <th>위험도</th><td>{riskLabel[assessment.level]} ({assessment.score} / 100)</td>
          </tr>
        </tbody>
      </table>
      <section className="report-section">
        <h2>평가 근거</h2>
        <p>{assessment.rationale}</p>
      </section>
      <section className="report-section">
        <h2>근거 법령</h2>
        {assessment.based_law.length ? (
          <ul>{assessment.based_law.map(x => <li key={x}>{x}</li>)}</ul>
        ) : (
          <p className="report-muted">확인된 근거 법령이 없습니다.</p>
        )}
      </section>
      <section className="report-section">
        <h2>권장 대응 조치</h2>
        {assessment.actions.length ? (
          <ol>{assessment.actions.map(x => <li key={x}>{x}</li>)}</ol>
        ) : (
          <p className="report-muted">권장 조치가 없습니다.</p>
        )}
      </section>
      <section className="report-section">
        <h2>상담 기록</h2>
        {messages.map((m, i) => (
          <div className="report-msg" key={m.id ?? i}>
            <b>{m.role === "assistant" ? "디딤" : "상담자"}</b>
            <span>{m.content}</span>
          </div>
        ))}
      </section>
      <section className="report-section">
        <h2>첨부 증거 자료</h2>
        {attachments.length ? (
          <ul>
            {attachments.map(a => (
              <li key={a.id}>{a.filename} ({formatBytes(a.size)}, {formatDate(a.created_at)})</li>
            ))}
          </ul>
        ) : (
          <p className="report-muted">첨부된 파일이 없습니다.</p>
        )}
      </section>
      <footer className="report-footer">
        <p>
          본 보고서는 입력된 상담 내용을 바탕으로 자동 생성된 참고 자료이며, 법률적·행정적 최종 판단이 아닙니다.<br />
          정확한 처리를 위해 학교 관리자 및 교원단체·법률 전문가의 검토를 받으시기 바랍니다.
        </p>
        <div className="report-signature">
          <div><span>작성자 확인</span><i /></div>
          <div><span>관리자 확인</span><i /></div>
        </div>
      </footer>
    </section>
  );
}
