// 최상위 화면 분기: 로그인 상태를 확인한 뒤 → 로그인 화면 또는 상담 화면.
// 상담 화면의 실제 내용은 workspace/ 폴더에 있다 (구조는 AGENTS.md "프런트엔드 구조" 참고).
import { useEffect, useState } from "react";

import { ApiError, getCurrentUser } from "./api";
import type { AuthUser } from "./api";
import LoginPage from "./LoginPage";
import Workspace from "./workspace/Workspace";


export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function checkSession() {
      try {
        const currentUser = await getCurrentUser();
        if (mounted) {
          setUser(currentUser);
        }
      } catch (caughtError) {
        if (caughtError instanceof ApiError && caughtError.status !== 401) {
          console.error("세션 확인 실패:", caughtError);
        }
        if (mounted) {
          setUser(null);
        }
      } finally {
        if (mounted) {
          setCheckingSession(false);
        }
      }
    }

    checkSession();

    return () => {
      mounted = false;
    };
  }, []);

  if (checkingSession) {
    return (
      <main className="session-loading">
        <div className="session-loading-logo">
          <img src="/icons/icon.svg"></img>
        </div>
        <p>로그인 상태를 확인하고 있습니다…</p>
      </main>
    );
  }

  if (!user) {
    return <LoginPage onLoggedIn={loggedInUser => setUser(loggedInUser)} />;
  }

  return <Workspace user={user} onLoggedOut={() => setUser(null)} />;
}