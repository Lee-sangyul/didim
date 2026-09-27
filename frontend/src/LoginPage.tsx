import {
    FormEvent,
    useState,
} from "react";

import {
    ApiError,
    login,
} from "./api";

import type {
    AuthUser,
} from "./api";


interface LoginPageProps {
    onLoggedIn: (user: AuthUser) => void;
}


export default function LoginPage({
    onLoggedIn,
}: LoginPageProps) {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");


    async function handleSubmit(
        event: FormEvent<HTMLFormElement>,
    ) {
        event.preventDefault();

        if (
            !username.trim()
            || !password
            || loading
        ) {
            return;
        }

        setLoading(true);
        setError("");

        try {
            const result = await login(
                username.trim(),
                password,
            );

            onLoggedIn(result.user);

        } catch (caughtError) {
            if (caughtError instanceof ApiError) {
                setError(caughtError.message);
            } else {
                setError(
                    "로그인 중 오류가 발생했습니다.",
                );
            }

        } finally {
            setLoading(false);
        }
    }


    return (
        <main className="login-page">
            <section className="login-panel">
                <div className="login-brand">
                    <div className="login-logo">
                        디
                    </div>

                    <div>
                        <h1>디딤</h1>
                        <p>교권 침해 상담 지원 시스템</p>
                    </div>
                </div>

                <div className="login-heading">
                    <span>교직원 전용</span>

                    <h2>로그인</h2>

                    <p>
                        관리자에게 발급받은 계정으로
                        로그인해 주세요.
                    </p>
                </div>

                <form
                    className="login-form"
                    onSubmit={handleSubmit}
                >
                    <label>
                        <span>아이디</span>

                        <input
                            type="text"
                            value={username}
                            onChange={(event) => {
                                setUsername(
                                    event.target.value,
                                );
                            }}
                            autoComplete="username"
                            minLength={3}
                            maxLength={50}
                            disabled={loading}
                            required
                            autoFocus
                        />
                    </label>

                    <label>
                        <span>비밀번호</span>

                        <input
                            type="password"
                            value={password}
                            onChange={(event) => {
                                setPassword(
                                    event.target.value,
                                );
                            }}
                            autoComplete="current-password"
                            maxLength={256}
                            disabled={loading}
                            required
                        />
                    </label>

                    {error && (
                        <div
                            className="login-error"
                            role="alert"
                        >
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        className="login-submit"
                        disabled={
                            loading
                            || !username.trim()
                            || !password
                        }
                    >
                        {loading
                            ? "로그인 중…"
                            : "로그인"}
                    </button>
                </form>

                <div className="login-security">
                    <span aria-hidden="true">
                        🔒
                    </span>

                    <p>
                        상담 내용은 로그인한 사용자별로
                        분리되어 저장됩니다.
                    </p>
                </div>

                <footer className="login-footer">
                    계정 발급 및 비밀번호 초기화는
                    시스템 관리자에게 문의하세요.
                </footer>
            </section>

            <aside className="login-intro">
                <div>
                    <span className="login-intro-label">
                        DIDIM
                    </span>

                    <h2>
                        혼자 감당하지
                        <br />
                        않아도 됩니다.
                    </h2>

                    <p>
                        상황 정리부터 위험도 분석,
                        대응 절차와 사건 보고서까지
                        교사의 다음 행동을 함께 준비합니다.
                    </p>
                </div>

                <ul>
                    <li>
                        <b>상담 분리</b>
                        <span>
                            다른 사용자의 상담은 조회할 수 없습니다.
                        </span>
                    </li>

                    <li>
                        <b>안전한 로그인</b>
                        <span>
                            비밀번호 원문과 세션 토큰을 저장하지 않습니다.
                        </span>
                    </li>

                    <li>
                        <b>근거 중심 안내</b>
                        <span>
                            위험도와 대응 절차를 구조화해 제공합니다.
                        </span>
                    </li>
                </ul>
            </aside>
        </main>
    );
}