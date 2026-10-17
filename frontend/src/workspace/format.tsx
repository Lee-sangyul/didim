// 화면에 보여 줄 값을 다듬는 순수 함수들 (상태·서버와 무관).
import type { ReactNode } from "react";

function renderInlineText(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|~~[^~]+~~|`[^`]+`)/g);

  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("*") && part.endsWith("*")) return <em key={index}>{part.slice(1, -1)}</em>;
    if (part.startsWith("~~") && part.endsWith("~~")) return <del key={index}>{part.slice(2, -2)}</del>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    return <span key={index}>{part}</span>;
  });
}

// 답변의 간단한 마크다운(굵게·기울임·취소선·코드)과 줄바꿈을 그린다.
export function renderText(text: string) {
  return text.split("\n").map((line, i) => (
    <span key={i}>
      {renderInlineText(line)}
      <br />
    </span>
  ));
}

export function formatBytes(size: number) {
  if (size < 1024) {
    return `${size}B`;
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)}KB`;
  }

  return `${(size / 1024 / 1024).toFixed(1)}MB`;
}

export function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString("ko-KR");
  } catch {
    return iso;
  }
}

// 브라우저 인쇄 창을 연다. 인쇄용 보고서(.report-print)만 보이도록 CSS(@media print)가 처리한다.
export function exportPrint() {
  window.print();
}
