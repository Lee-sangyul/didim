import type { Citation } from "./types";

export default function CitationCards({
  citations,
}: {
  citations: Citation[];
}) {
  if (citations.length === 0) {
    return null;
  }

  const asOf = citations[0].as_of;

  return (
    <section className="result citations">
      <label>근거 조문</label>
      <div>
        {citations.map(c => (
          <details key={c.article_id} className="citation-card">
            <summary>
              <strong>{c.law_name} {c.article_no}</strong>
              {c.title && <span> {c.title}</span>}
            </summary>
            <pre className="citation-text">{c.text}</pre>
            <p className="citation-reason">
              <em>선택 이유</em> {c.reason}
            </p>
            <a href={c.source_url} target="_blank" rel="noreferrer">
              국가법령정보센터에서 보기
            </a>
          </details>
        ))}
        <p className="citation-notice">
          조문 기준일: {asOf} · 법 개정에 따라 내용이 달라질 수 있으며,
          법률 자문이 아닌 참고 자료입니다.
        </p>
      </div>
    </section>
  );
}
