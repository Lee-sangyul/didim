// 입력창(textarea)이 내용의 줄 수에 맞춰 1~TEXTAREA_MAX_LINES줄로 늘어나게 한다.
// 높이는 CSS가 아니라 여기서 계산해 인라인으로 지정한다(CSS는 모양만 담당: .input / .input.multiline).
import { useCallback, useEffect, useRef, useState } from "react";

import { TEXTAREA_MAX_LINES } from "../constants";

export function useAutoGrowTextarea(value: string) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // 2줄 이상이면 true. 입력 상자 모양(알약형 ↔ 둥근 사각형)을 바꾸는 데 쓴다.
  const [multiline, setMultiline] = useState(false);

  // 내용의 실제 줄 수(줄바꿈·자동 줄바꿈 포함)에 맞춰 늘리고, 그보다 길면 스크롤한다.
  // 타이핑·음성 입력·전송 후 비우기 모두 value가 바뀌므로 한 곳에서 처리.
  const fitTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;

    const lineHeight = parseFloat(getComputedStyle(el).lineHeight) || 24;
    el.style.height = `${lineHeight}px`; // 한 줄 높이로 줄여야 scrollHeight가 내용 높이를 정확히 반영한다
    const contentLines = Math.max(1, Math.round(el.scrollHeight / lineHeight));
    const lines = Math.min(contentLines, TEXTAREA_MAX_LINES);

    el.style.height = `${lines * lineHeight}px`;
    el.style.overflowY = contentLines > TEXTAREA_MAX_LINES ? "auto" : "hidden";
    setMultiline(lines > 1);
  }, []);

  useEffect(() => {
    fitTextarea();
  }, [value, fitTextarea]);

  // 창 크기·사이드 패널 토글로 너비가 바뀌면 자동 줄바꿈이 달라지므로 다시 맞춘다
  useEffect(() => {
    const el = textareaRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;

    let lastWidth = el.clientWidth;
    const observer = new ResizeObserver(() => {
      if (el.clientWidth !== lastWidth) {
        lastWidth = el.clientWidth;
        fitTextarea();
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [fitTextarea]);

  return { textareaRef, multiline };
}
