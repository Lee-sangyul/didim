// 대화 목록(.thread)의 스크롤: 새 메시지가 오면 맨 아래로 따라가고,
// 사용자가 위쪽을 보고 있으면 "↓ 새 답변" 버튼만 띄운다.
import { MutableRefObject, useEffect, useRef, useState } from "react";

import type { Message } from "../../types";

/**
 * @param messages 바뀔 때마다 스크롤 여부를 판단한다
 * @param stickToBottom "맨 아래를 따라갈지" 표시하는 ref. 상담을 열거나 보낼 때
 *                      useWorkspace가 true로 바꿔 두므로 같은 ref를 함께 쓴다.
 */
export function useThreadScroll(messages: Message[], stickToBottom: MutableRefObject<boolean>) {
  const thread = useRef<HTMLDivElement>(null);
  const [showNewAnswer, setShowNewAnswer] = useState(false);

  function scrollToBottom(behavior: ScrollBehavior = "auto") {
    const el = thread.current;
    if (!el) return;
    stickToBottom.current = true;
    el.scrollTo({ top: el.scrollHeight, behavior });
    setShowNewAnswer(false);
  }

  function onThreadScroll() {
    const el = thread.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    stickToBottom.current = nearBottom;
    if (nearBottom) setShowNewAnswer(false);
  }

  useEffect(() => {
    if (stickToBottom.current) scrollToBottom();
    else setShowNewAnswer(true);
  }, [messages]);

  return { thread, showNewAnswer, scrollToBottom, onThreadScroll };
}
