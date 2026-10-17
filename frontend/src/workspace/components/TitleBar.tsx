// 맨 위 띠: 로고, 현재 사용자, (관리자면) 계정 관리 버튼, 로그아웃.
import type { AuthUser } from "../../api";

interface Props {
  user: AuthUser;
  darkMode: boolean;
  loggingOut: boolean;
  onLogout: () => void;
}

export default function TitleBar({ user, darkMode, loggingOut, onLogout }: Props) {
  return (
    <header className={`titlebar ${darkMode ? "dark-mode" : ""}`}>
      <img className="logo-sm" src="/icons/icon.svg" alt="디딤" />
      디딤 — 교권 침해 상담 도우미
      <span className="title-space" />
      <span className="status">CLOUD</span>
      <span className="current-user">
        {user.name} · {user.role === "admin" ? "관리자" : "교사"}
      </span>

      {(
        user.role === "admin"
        || user.role === "super_admin"
      ) && (
          <button
            type="button"
            className="admin-page-button"
            onClick={() => {
              window.location.href = "/admin/registrations";
            }}
          >
            계정 관리
          </button>
        )}

      <button
        type="button"
        className="logout-button"
        onClick={onLogout}
        disabled={loggingOut}
      >
        {loggingOut ? "로그아웃 중…" : "로그아웃"}
      </button>
    </header>
  );
}
