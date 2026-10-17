// 대화 목록 영역: "↓ 새 답변" 버튼, 비어 있을 때의 안내, 메시지들.
import type { RefObject } from "react";

import type { Message } from "../../types";
import MessageItem from "./MessageItem";

interface Props {
  threadRef: RefObject<HTMLDivElement | null>;
  onScroll: () => void;
  showNewAnswer: boolean;
  onScrollToNew: () => void;
  messages: Message[]; // 안내 문구만 있는 상태는 비운 채로 넘긴다 (Workspace의 visibleMessages)
  emptyTitle: string;
  loading: boolean;
  responseTime: number | null;
  bookmarks: number[];
  activeVersions: Record<number, number>;
  regenerating: { id: number; text: string } | null;
  onCopy: (text: string) => void;
  onToggleBookmark: (messageId: number) => void;
  onRegenerate: (message: Message) => void;
  onChangeVersion: (messageId: number, delta: number, count: number) => void;
}

export default function MessageThread({
  threadRef, onScroll, showNewAnswer, onScrollToNew, messages, emptyTitle,
  loading, responseTime, bookmarks, activeVersions, regenerating,
  onCopy, onToggleBookmark, onRegenerate, onChangeVersion,
}: Props) {
  return (
    <div className="thread" ref={threadRef} onScroll={onScroll}>
      {showNewAnswer && (
        <button type="button" className="new-answer-btn" onClick={onScrollToNew}>↓ 새 답변</button>
      )}

      {messages.length === 0 && (
        <div className="empty">
          <div className="empty-logo"><img src="/icons/icon.svg" alt="디딤" /></div>
          <h2>{emptyTitle}</h2>
          <p>
            새 상담을 시작하고 상황을 편하게 적어 주세요.<br />
            학생·학부모의 실명과 연락처는 입력하지 마세요.
          </p>
        </div>
      )}

      {messages.map((m, i) => (
        <MessageItem
          key={m.id ?? i}
          message={m}
          isLast={i === messages.length - 1}
          loading={loading}
          responseTime={responseTime}
          bookmarked={m.id != null && bookmarks.includes(m.id)}
          activeVersion={m.id != null ? activeVersions[m.id] : undefined}
          regeneratingText={regenerating && regenerating.id === m.id ? regenerating.text : undefined}
          onCopy={onCopy}
          onToggleBookmark={onToggleBookmark}
          onRegenerate={onRegenerate}
          onChangeVersion={onChangeVersion}
        />
      ))}
    </div>
  );
}
