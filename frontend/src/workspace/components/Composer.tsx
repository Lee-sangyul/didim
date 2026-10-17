// 아래쪽 입력창: 파일 첨부(+), 글 입력(자동으로 늘어남), 음성 입력, 전송.
// Enter = 전송, Shift+Enter = 줄바꿈 (한글 조합 중에는 전송하지 않는다).
import type { Dispatch, FormEvent, RefObject, SetStateAction } from "react";

import { MIN_MESSAGE_LENGTH } from "../constants";

interface Props {
  input: string;
  setInput: Dispatch<SetStateAction<string>>;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  multiline: boolean; // 2줄 이상이면 둥근 사각형 모양 (useAutoGrowTextarea)
  loading: boolean;
  uploading: boolean;
  isListening: boolean;
  fileInput: RefObject<HTMLInputElement | null>; // 숨겨진 파일 선택창 (Workspace가 가지고 있다)
  onSend: (e?: FormEvent) => void;
  onToggleVoice: () => void;
}

export default function Composer({
  input, setInput, textareaRef, multiline, loading, uploading, isListening, fileInput, onSend, onToggleVoice,
}: Props) {
  return (
    <form className="composer" onSubmit={onSend}>
      <div className={`input${multiline ? " multiline" : ""}`}>
        <button
          type="button"
          className="attach-btn"
          aria-label="첨부자료 추가"
          title="첨부자료 추가"
          disabled={uploading}
          onClick={() => fileInput.current?.click()}
        >
          +
        </button>

        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              onSend();
            }
          }}
          rows={1}
          placeholder={isListening ? "말씀해 주세요…" : "상황을 자세히 적어 주세요…"}
          maxLength={8000}
        />

        <div className="input-actions">
          <button
            type="button"
            className={`voice-btn ${isListening ? "listening" : ""}`}
            onClick={onToggleVoice}
            disabled={loading}
            aria-label={isListening ? "음성 입력 중지" : "음성 입력 시작"}
            title={isListening ? "음성 입력 중지" : "음성으로 입력"}
          >
            {isListening ? (
              <span className="listening-icon">■</span>
            ) : (
              <img src="/mic.png" alt="음성 입력" className="mic-image" />
            )}
          </button>

          <button type="submit" className="send-btn" disabled={loading || input.trim().length < MIN_MESSAGE_LENGTH}>
            {loading ? "…" : "➜"}
          </button>
        </div>
      </div>
      <small>일반적인 안내 도구이며 구체적인 판단은 교원단체·법률 전문가의 검토가 필요합니다.</small>
    </form>
  );
}
