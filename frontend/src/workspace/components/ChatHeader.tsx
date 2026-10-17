// 대화 영역 위쪽: 상담 제목과 버튼들(결과 접기, 다크 모드, 삭제, 내보내기).
import type { CaseItem } from "../../types";

interface Props {
  active: CaseItem | undefined;
  selected: number | null;
  asideOpen: boolean;
  darkMode: boolean;
  onToggleRail: () => void;
  onToggleAside: () => void;
  onToggleDarkMode: () => void;
  onDelete: () => void;
  onPrint: () => void;
}

export default function ChatHeader({
  active, selected, asideOpen, darkMode,
  onToggleRail, onToggleAside, onToggleDarkMode, onDelete, onPrint,
}: Props) {
  return (
    <div className="chat-head">
      <button className="menu-btn" aria-label="상담 목록" onClick={onToggleRail}>☰</button>
      <div>
        <h1>
          {active?.title ?? "새 상담"}
        </h1>

        <small>
          {active
            ? `사건 #${String(active.id).padStart(
              4,
              "0",
            )}`
            : "상담을 시작하세요"}
        </small>
      </div>
      <span />
      <button onClick={onToggleAside}>{asideOpen ? "결과 접기" : "결과 보기"}</button>
      <button type="button" onClick={onToggleDarkMode} title={darkMode ? "라이트 모드" : "다크 모드"}>
        {darkMode ? "☀️" : "🌙"}
      </button>
      <button onClick={onDelete} disabled={!selected}>삭제</button>
      <button onClick={onPrint}>내보내기</button>
    </div>
  );
}
