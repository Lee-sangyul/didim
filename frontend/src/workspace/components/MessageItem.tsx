// 대화 한 건(말풍선) + 답변 아래 버튼들(복사·북마크·다시 생성·버전 이동).
// 어떤 버전을 보여 줄지는 여기서 계산하고, 동작은 전부 props로 받은 함수를 부른다.
import type { Message } from "../../types";
import { renderText } from "../format";
import { versionsOf } from "../versions";

interface Props {
  message: Message;
  isLast: boolean; // 대화의 마지막 메시지인가 (다시 생성·응답 시간은 마지막에만)
  loading: boolean;
  responseTime: number | null;
  bookmarked: boolean;
  /** 보고 있는 버전 번호(0부터). 없으면 최신 */
  activeVersion: number | undefined;
  /** 다시 생성 중이면 그 스트리밍 텍스트, 아니면 undefined */
  regeneratingText: string | undefined;
  onCopy: (text: string) => void;
  onToggleBookmark: (messageId: number) => void;
  onRegenerate: (message: Message) => void;
  onChangeVersion: (messageId: number, delta: number, count: number) => void;
}

export default function MessageItem({
  message: m, isLast, loading, responseTime, bookmarked, activeVersion, regeneratingText,
  onCopy, onToggleBookmark, onRegenerate, onChangeVersion,
}: Props) {
  const versions = versionsOf(m);
  const versionsCount = versions.length;
  const activeIdx = Math.min(
    m.id != null ? (activeVersion ?? versionsCount - 1) : versionsCount - 1,
    versionsCount - 1,
  );
  const displayedContent =
    regeneratingText !== undefined
      ? regeneratingText
      : (versions[activeIdx] ?? m.content);
  const currentVersionNum = activeIdx + 1;

  return (
    <article className={`message ${m.role}`}>
      <div className="avatar">
        {m.role === "assistant" ? <img src="/icons/icon.svg" alt="디딤" /> : "나"}
      </div>
      <div className="bubble">
        {renderText(displayedContent || "답변을 정리하고 있습니다…")}

        {m.role === "assistant" && m.content && !loading && (
          <div className="message-actions">
            {responseTime !== null && isLast && (
              <span className="response-time">답변 완료 · {responseTime.toFixed(1)}초</span>
            )}
            <button
              type="button"
              className="copy-btn"
              onClick={() => onCopy(displayedContent)}
              title="답변 복사"
              aria-label="답변 복사"
            >
              <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="9" y="9" width="11" height="11" rx="2" />
                <path d="M5 15V6a2 2 0 0 1 2-2h9" />
              </svg>
            </button>
            {m.id != null && (
              <button
                type="button"
                className={`bookmark-btn ${bookmarked ? "on" : ""}`}
                onClick={() => onToggleBookmark(m.id!)}
                title={bookmarked ? "북마크 해제" : "북마크"}
                aria-label={bookmarked ? "북마크 해제" : "북마크"}
                aria-pressed={bookmarked}
              >
                <svg viewBox="0 0 24 24" width="17" height="17" fill={bookmarked ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M7 4h10a1 1 0 0 1 1 1v15l-6-4-6 4V5a1 1 0 0 1 1-1z" />
                </svg>
              </button>
            )}
            {!m.content.includes("안녕하세요. 겪고 계신 상황을 시간 순서대로 적어 주세요") && (
              <>
                {/* 서버는 마지막 답변만 다시 생성할 수 있다. 버전 이동은 모든 답변에서 가능 */}
                {isLast && (
                  <button
                    type="button"
                    className="regenerate-btn"
                    onClick={() => onRegenerate(m)}
                    title="답변 다시 생성하기"
                    aria-label="답변 다시 생성하기"
                  >
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.73-5.73" />
                    </svg>
                  </button>
                )}
                {versionsCount >= 2 && (
                  <span className="version-nav">
                    <button
                      type="button"
                      onClick={() => onChangeVersion(m.id!, -1, versionsCount)}
                      disabled={currentVersionNum <= 1}
                    >
                      &lt;
                    </button>
                    <span>{currentVersionNum}/{versionsCount}</span>
                    <button
                      type="button"
                      onClick={() => onChangeVersion(m.id!, 1, versionsCount)}
                      disabled={currentVersionNum >= versionsCount}
                    >
                      &gt;
                    </button>
                  </span>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
