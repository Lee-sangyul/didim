// 상담 화면 전체를 "조립"하는 파일. 여기에는 로직을 쌓지 않는다.
//   - 데이터·서버 동작  → hooks/useWorkspace
//   - 화면 보조 동작    → hooks/ (음성 입력, 입력창 높이, 스크롤, 북마크, 패널 너비)
//   - 화면 조각         → components/
// 이 파일이 맡는 것은 (1) 훅을 부르고 (2) 화면 조각에 필요한 값을 나눠 주고 (3) 화면 전용 상태(패널 열림·다크 모드)를 갖는 것뿐이다.
import { CSSProperties, FormEvent, useRef, useState } from "react";

import type { AuthUser } from "../api";
import Composer from "./components/Composer";
import CaseRail from "./components/CaseRail";
import ChatHeader from "./components/ChatHeader";
import MessageThread from "./components/MessageThread";
import PrintReport from "./components/PrintReport";
import ResultPanel from "./components/ResultPanel";
import TitleBar from "./components/TitleBar";
import { MOBILE_MAX_WIDTH } from "./constants";
import { exportPrint } from "./format";
import { useAutoGrowTextarea } from "./hooks/useAutoGrowTextarea";
import { useBookmarks } from "./hooks/useBookmarks";
import { usePanelResize } from "./hooks/usePanelResize";
import { useThreadScroll } from "./hooks/useThreadScroll";
import { useVoiceInput } from "./hooks/useVoiceInput";
import { useWorkspace } from "./hooks/useWorkspace";

interface WorkspaceProps {
  user: AuthUser;
  onLoggedOut: () => void;
}

export default function Workspace({ user, onLoggedOut }: WorkspaceProps) {
  const ws = useWorkspace({ onLoggedOut });
  const { bookmarks, toggleBookmark } = useBookmarks();
  const { textareaRef, multiline } = useAutoGrowTextarea(ws.input);
  const { isListening, toggleVoiceInput } = useVoiceInput(ws.setInput, ws.setError);
  const { thread, showNewAnswer, scrollToBottom, onThreadScroll } = useThreadScroll(ws.messages, ws.stickToBottom);
  const { asideWidth, setAsideWidth, railWidth, railResizerProps, asideResizerProps } = usePanelResize();

  // 화면 전용 상태 (서버와 무관)
  // 오른쪽 결과 패널 열림. 폰 폭에서는 패널이 화면을 덮는 오버레이라서 닫힌 채로 시작한다(☰·입력창 가림 방지, R022).
  const [aside, setAside] = useState(() => window.innerWidth > MOBILE_MAX_WIDTH);
  const [railOpen, setRailOpen] = useState(false); // 좁은 화면에서 왼쪽 목록 열림
  const [darkMode, setDarkMode] = useState(false);

  // 첨부 입력은 하나만 두고 입력창(+)과 결과 패널의 버튼이 같이 사용한다
  const fileInput = useRef<HTMLInputElement>(null);

  async function copyAnswer(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      ws.flashMessage("AI 답변이 복사되었습니다.");
    } catch {
      ws.setError("답변을 복사하지 못했습니다.");
    }
  }

  // 상담을 새로 열거나 고르면 좁은 화면의 목록 패널을 닫는다 (성공했을 때만)
  async function addCase() {
    if (await ws.addCase()) setRailOpen(false);
  }

  async function choose(id: number) {
    if (await ws.choose(id)) setRailOpen(false);
  }

  return (
    <main className="app-shell">
      <TitleBar user={user} darkMode={darkMode} loggingOut={ws.loggingOut} onLogout={ws.handleLogout} />

      <div
        className={`layout ${aside ? "" : "aside-closed"} ${darkMode ? "dark-mode" : ""}`}
        style={{ "--aside-width": `${asideWidth}px`, "--rail-width": `${railWidth}px` } as CSSProperties}
      >
        {railOpen && <div className="rail-backdrop show" onClick={() => setRailOpen(false)} />}
        {!aside && (
          <button
            type="button"
            className="aside-reopen-btn"
            onClick={() => setAside(true)}
            aria-label="상담 결과 열기"
            title="상담 결과 열기"
          >
            ‹
          </button>
        )}

        <CaseRail cases={ws.cases} selected={ws.selected} open={railOpen} onAddCase={addCase} onChoose={choose} />

        <div className="rail-resizer" {...railResizerProps} />

        <section className="chat">
          <ChatHeader
            active={ws.active}
            selected={ws.selected}
            asideOpen={aside}
            darkMode={darkMode}
            onToggleRail={() => setRailOpen(x => !x)}
            onToggleAside={() => setAside(x => !x)}
            onToggleDarkMode={() => setDarkMode(x => !x)}
            onDelete={ws.deleteCase}
            onPrint={exportPrint}
          />

          <MessageThread
            threadRef={thread}
            onScroll={onThreadScroll}
            showNewAnswer={showNewAnswer}
            onScrollToNew={() => scrollToBottom("smooth")}
            messages={ws.visibleMessages}
            emptyTitle={ws.emptyTitle}
            loading={ws.loading}
            responseTime={ws.responseTime}
            bookmarks={bookmarks}
            activeVersions={ws.activeVersions}
            regenerating={ws.regenerating}
            onCopy={copyAnswer}
            onToggleBookmark={toggleBookmark}
            onRegenerate={ws.regenerateAnswer}
            onChangeVersion={ws.changeVersion}
          />

          {ws.error && <div className="error">{ws.error}</div>}

          <input ref={fileInput} type="file" className="file-hidden" onChange={ws.onUpload} />

          <Composer
            input={ws.input}
            setInput={ws.setInput}
            textareaRef={textareaRef}
            multiline={multiline}
            loading={ws.loading}
            uploading={ws.uploading}
            isListening={isListening}
            fileInput={fileInput}
            onSend={(e?: FormEvent) => ws.send(e)}
            onToggleVoice={toggleVoiceInput}
          />
        </section>

        {aside && (
          <ResultPanel
            assessment={ws.assessment}
            attachments={ws.attachments}
            uploading={ws.uploading}
            asideWidth={asideWidth}
            resizerProps={asideResizerProps}
            fileInput={fileInput}
            onResetWidth={setAsideWidth}
            onClose={() => setAside(false)}
            onDeleteAttachment={ws.onDeleteAttachment}
            onPrint={exportPrint}
          />
        )}
      </div>

      {ws.active && (
        <PrintReport
          active={ws.active}
          assessment={ws.assessment}
          messages={ws.visibleMessages}
          attachments={ws.attachments}
        />
      )}
    </main>
  );
}
