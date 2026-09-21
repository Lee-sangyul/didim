import {
  ChangeEvent,
  FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  ApiError,
  attachmentDownloadUrl,
  createCase,
  getCurrentUser,
  getLatestAssessment,
  getMessages,
  listAttachments,
  listCases,
  logout,
  removeAttachment,
  removeCase,
  streamChat,
  uploadAttachment,
} from "./api";

import type {
  AuthUser,
} from "./api";

import LoginPage from "./LoginPage";

import type {
  Assessment,
  Attachment,
  CaseItem,
  Message,
  RiskLevel,
} from "./types";


const riskLabel: Record<RiskLevel, string> = {
  low: "낮음",
  caution: "주의",
  danger: "위험",
  emergency: "긴급",
};


const initialAssessment: Assessment = {
  level: "low",
  score: 0,
  category: "분석 전",
  rationale:
    "상황을 입력하면 위험도와 대응 절차를 정리합니다.",
  actions: [],
  based_law: [],
};


function renderText(text: string) {
  return text.split("\n").map((line, index) => (
    <span key={index}>
      {line.replaceAll("**", "")}
      <br />
    </span>
  ));
}


function formatBytes(size: number) {
  if (size < 1024) {
    return `${size}B`;
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)}KB`;
  }

  return `${(size / 1024 / 1024).toFixed(1)}MB`;
}


function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString("ko-KR");
  } catch {
    return iso;
  }
}


interface WorkspaceProps {
  user: AuthUser;
  onLoggedOut: () => void;
}


function Workspace({
  user,
  onLoggedOut,
}: WorkspaceProps) {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [selected, setSelected] = useState<number | null>(
    null,
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [assessment, setAssessment] =
    useState<Assessment>(initialAssessment);
  const [loading, setLoading] = useState(false);
  const [aside, setAside] = useState(true);
  const [error, setError] = useState("");
  const [attachments, setAttachments] = useState<
    Attachment[]
  >([]);
  const [uploading, setUploading] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  const thread = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const active = cases.find(
    (caseItem) => caseItem.id === selected,
  );


  function handleApiError(caughtError: unknown) {
    if (
      caughtError instanceof ApiError
      && caughtError.status === 401
    ) {
      onLoggedOut();
      return;
    }

    if (caughtError instanceof Error) {
      setError(caughtError.message);
      return;
    }

    setError("요청을 처리하는 중 오류가 발생했습니다.");
  }


  async function loadAttachments(id: number) {
    try {
      setAttachments(
        await listAttachments(id),
      );
    } catch (caughtError) {
      if (
        caughtError instanceof ApiError
        && caughtError.status === 401
      ) {
        onLoggedOut();
        return;
      }

      setAttachments([]);
    }
  }


  async function loadAssessment(
    id: number,
    fallback?: CaseItem,
  ) {
    const latest = await getLatestAssessment(id);

    if (latest) {
      setAssessment({
        level: latest.risk_level as RiskLevel,
        score: latest.risk_score,
        category: latest.category,
        rationale: latest.rationale,
        actions: latest.actions,
        based_law: latest.based_law,
      });

      return;
    }

    if (fallback) {
      setAssessment({
        ...initialAssessment,
        level: fallback.risk_level,
        score: fallback.risk_score,
        category: fallback.category,
        based_law: fallback.based_law,
      });

      return;
    }

    setAssessment(initialAssessment);
  }


  async function refresh(prefer?: number) {
    const allCases = await listCases();

    setCases(allCases);

    const id = (
      prefer
      ?? selected
      ?? allCases[0]?.id
    );

    if (!id) {
      setSelected(null);
      setMessages([]);
      setAttachments([]);
      setAssessment(initialAssessment);
      return;
    }

    setSelected(id);

    const [
      loadedMessages,
    ] = await Promise.all([
      getMessages(id),
      loadAssessment(
        id,
        allCases.find(
          (caseItem) => caseItem.id === id,
        ),
      ),
      loadAttachments(id),
    ]);

    setMessages(loadedMessages);
  }


  useEffect(() => {
    refresh().catch((caughtError) => {
      handleApiError(caughtError);
    });
  }, []);


  useEffect(() => {
    thread.current?.scrollTo({
      top: thread.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);


  async function addCase() {
    try {
      setError("");

      const createdCase = await createCase();

      setAssessment(initialAssessment);
      setAttachments([]);

      await refresh(createdCase.id);

      setRailOpen(false);
    } catch (caughtError) {
      handleApiError(caughtError);
    }
  }


  async function choose(id: number) {
    try {
      setError("");
      setSelected(id);

      const loadedMessages = await getMessages(id);

      setMessages(loadedMessages);

      await loadAssessment(
        id,
        cases.find(
          (caseItem) => caseItem.id === id,
        ),
      );

      await loadAttachments(id);

      setRailOpen(false);
    } catch (caughtError) {
      handleApiError(caughtError);
    }
  }


  async function deleteCase() {
    if (
      !selected
      || !confirm("이 상담 기록을 삭제할까요?")
    ) {
      return;
    }

    try {
      setError("");

      await removeCase(selected);

      setSelected(null);
      setMessages([]);
      setAttachments([]);
      setAssessment(initialAssessment);

      await refresh();
    } catch (caughtError) {
      handleApiError(caughtError);
    }
  }


  async function send(event?: FormEvent) {
    event?.preventDefault();

    if (!input.trim() || loading) {
      return;
    }

    let id = selected;

    try {
      if (!id) {
        const createdCase = await createCase();

        id = createdCase.id;
        setSelected(id);
      }

      const content = input.trim();

      setInput("");
      setError("");
      setLoading(true);

      setMessages((currentMessages) => [
        ...currentMessages,
        {
          case_id: id!,
          role: "user",
          content,
        },
        {
          case_id: id!,
          role: "assistant",
          content: "",
        },
      ]);

      const result = await streamChat(
        id,
        content,
        (text) => {
          setMessages((currentMessages) =>
            currentMessages.map(
              (message, index) =>
                index === currentMessages.length - 1
                  ? {
                      ...message,
                      content: message.content + text,
                    }
                  : message,
            ),
          );
        },
      );

      setAssessment(result);

      await refresh(id);
    } catch (caughtError) {
      handleApiError(caughtError);

      setMessages((currentMessages) =>
        currentMessages.slice(0, -1),
      );
    } finally {
      setLoading(false);
    }
  }


  function exportPrint() {
    window.print();
  }


  async function onUpload(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0];

    event.target.value = "";

    if (!file) {
      return;
    }

    let id = selected;

    try {
      if (!id) {
        const createdCase = await createCase();

        id = createdCase.id;
        setSelected(id);

        await refresh(id);
      }

      setUploading(true);
      setError("");

      await uploadAttachment(id, file);
      await loadAttachments(id);
    } catch (caughtError) {
      handleApiError(caughtError);
    } finally {
      setUploading(false);
    }
  }


  async function onDeleteAttachment(
    attachmentId: number,
  ) {
    if (!selected) {
      return;
    }

    try {
      setError("");

      await removeAttachment(
        selected,
        attachmentId,
      );

      await loadAttachments(selected);
    } catch (caughtError) {
      handleApiError(caughtError);
    }
  }


  async function handleLogout() {
    if (loggingOut) {
      return;
    }

    setLoggingOut(true);
    setError("");

    try {
      await logout();
    } catch (caughtError) {
      if (
        !(caughtError instanceof ApiError)
        || caughtError.status !== 401
      ) {
        handleApiError(caughtError);
        setLoggingOut(false);
        return;
      }
    }

    onLoggedOut();
  }


  return (
    <main className="app-shell">
      <header className="titlebar">
        <span className="logo-sm" />

        디딤 — 교권 침해 상담 도우미

        <span className="title-space" />

        <span className="status">
          CLOUD
        </span>

        <span className="current-user">
          {user.name} · {
            user.role === "admin"
              ? "관리자"
              : "교사"
          }
        </span>

        <button
          type="button"
          className="logout-button"
          onClick={handleLogout}
          disabled={loggingOut}
        >
          {loggingOut
            ? "로그아웃 중…"
            : "로그아웃"}
        </button>
      </header>

      <div
        className={
          `layout ${aside ? "" : "aside-closed"}`
        }
      >
        {railOpen && (
          <div
            className="rail-backdrop show"
            onClick={() => setRailOpen(false)}
          />
        )}

        <nav
          className={
            `rail ${railOpen ? "open" : ""}`
          }
        >
          <div className="brand">
            <div className="logo">
              디
            </div>

            <div>
              <b>디딤</b>
              <small>교권 침해 상담</small>
            </div>
          </div>

          <button
            className="new"
            onClick={addCase}
          >
            ＋ 새 상담 시작
          </button>

          <div className="rail-label">
            최근 상담
          </div>

          <div className="case-list">
            {cases.map((caseItem) => (
              <button
                className={
                  `case ${
                    selected === caseItem.id
                      ? "active"
                      : ""
                  }`
                }
                onClick={() => choose(caseItem.id)}
                key={caseItem.id}
              >
                <i className={caseItem.risk_level} />

                <span>
                  <b>{caseItem.title}</b>

                  <small>
                    {caseItem.category}
                    {" · "}
                    {caseItem.risk_score}점
                  </small>
                </span>
              </button>
            ))}
          </div>

          <div className="privacy">
            🔒 상담은 사용자별로 분리되어 저장됩니다.
          </div>
        </nav>

        <section className="chat">
          <div className="chat-head">
            <button
              className="menu-btn"
              aria-label="상담 목록"
              onClick={() =>
                setRailOpen((current) => !current)
              }
            >
              ☰
            </button>

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

            <button
              onClick={() =>
                setAside((current) => !current)
              }
            >
              {aside
                ? "결과 접기"
                : "결과 보기"}
            </button>

            <button
              onClick={deleteCase}
              disabled={!selected}
            >
              삭제
            </button>

            <button onClick={exportPrint}>
              내보내기
            </button>
          </div>

          <div
            className="thread"
            ref={thread}
          >
            {messages.length === 0 && (
              <div className="empty">
                <div className="empty-logo">
                  디
                </div>

                <h2>
                  혼자 감당하지 않아도 됩니다
                </h2>

                <p>
                  새 상담을 시작하고 상황을
                  시간 순서대로 적어 주세요.
                  <br />
                  학생·학부모의 실명과 연락처는
                  입력하지 마세요.
                </p>
              </div>
            )}

            {messages.map((message, index) => (
              <article
                className={`message ${message.role}`}
                key={message.id ?? index}
              >
                <div className="avatar">
                  {message.role === "assistant"
                    ? "디"
                    : "나"}
                </div>

                <div className="bubble">
                  {renderText(
                    message.content
                    || "답변을 정리하고 있습니다…",
                  )}
                </div>
              </article>
            ))}
          </div>

          {error && (
            <div className="error">
              {error}
            </div>
          )}

          <form
            className="composer"
            onSubmit={send}
          >
            <div className="input">
              <textarea
                value={input}
                onChange={(event) =>
                  setInput(event.target.value)
                }
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter"
                    && !event.shiftKey
                  ) {
                    event.preventDefault();
                    send();
                  }
                }}
                placeholder="상황을 자세히 적어 주세요…"
                maxLength={8000}
              />

              <button
                disabled={
                  loading
                  || input.trim().length < 2
                }
              >
                {loading ? "…" : "➜"}
              </button>
            </div>

            <small>
              일반적인 안내 도구이며 구체적인 판단은
              교원단체·법률 전문가의 검토가 필요합니다.
            </small>
          </form>
        </section>

        {aside && (
          <aside className="aside">
            <div className="aside-head">
              <div>
                <h2>상담 결과</h2>
                <small>
                  입력 내용 기반 임시 분석
                </small>
              </div>

              <button
                onClick={() => setAside(false)}
              >
                ›
              </button>
            </div>

            <div className="aside-scroll">
              <div className="meta">
                <span>분류</span>
                <b>{assessment.category}</b>
              </div>

              <section
                className={
                  `risk ${assessment.level}`
                }
              >
                <label>위험도</label>

                <div className="risk-card">
                  <div>
                    <strong>
                      {riskLabel[assessment.level]}
                    </strong>

                    <b>
                      {assessment.score} / 100
                    </b>
                  </div>

                  <div className="gauge">
                    <i
                      style={{
                        width:
                          `${assessment.score}%`,
                      }}
                    />
                  </div>

                  <p>
                    {assessment.rationale}
                  </p>
                </div>
              </section>

              <section className="result">
                <label>대응 권고</label>

                <div>
                  {assessment.actions.length ? (
                    <ol>
                      {assessment.actions.map(
                        (action) => (
                          <li key={action}>
                            {action}
                          </li>
                        ),
                      )}
                    </ol>
                  ) : (
                    <p>
                      상담을 진행하면 단계별
                      조치가 표시됩니다.
                    </p>
                  )}
                </div>
              </section>

              {assessment.based_law.length > 0 && (
                <section className="result">
                  <label>근거 법령</label>

                  <div>
                    <ul className="law-list">
                      {assessment.based_law.map(
                        (law) => (
                          <li key={law}>
                            {law}
                          </li>
                        ),
                      )}
                    </ul>
                  </div>
                </section>
              )}

              <section className="attachments">
                <label>증거 자료</label>

                <div>
                  <input
                    ref={fileInput}
                    type="file"
                    className="file-hidden"
                    onChange={onUpload}
                  />

                  <button
                    type="button"
                    className="upload-btn"
                    disabled={uploading}
                    onClick={() =>
                      fileInput.current?.click()
                    }
                  >
                    {uploading
                      ? "업로드 중…"
                      : "📎 파일 첨부"}
                  </button>

                  {attachments.length > 0 && (
                    <ul className="file-list">
                      {attachments.map(
                        (attachment) => (
                          <li key={attachment.id}>
                            <a
                              href={attachmentDownloadUrl(
                                attachment.case_id,
                                attachment.id,
                              )}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {attachment.filename}
                            </a>

                            <small>
                              {formatBytes(
                                attachment.size,
                              )}
                            </small>

                            <button
                              type="button"
                              onClick={() =>
                                onDeleteAttachment(
                                  attachment.id,
                                )
                              }
                            >
                              ✕
                            </button>
                          </li>
                        ),
                      )}
                    </ul>
                  )}
                </div>
              </section>

              <section className="notice">
                <b>꼭 확인하세요</b>

                <p>
                  법령과 절차는 개정될 수 있습니다.
                  이 앱의 결과만으로 신고·징계·법적
                  조치를 결정하지 마세요.
                </p>
              </section>
            </div>

            <div className="aside-actions">
              <button onClick={exportPrint}>
                PDF로 인쇄
              </button>
            </div>
          </aside>
        )}
      </div>

      {active && (
        <section className="report-print">
          <header className="report-head">
            <h1>
              교권 침해 상담 사건 보고서
            </h1>

            <p>
              Case Report for Teacher-Rights
              Infringement Consultation
            </p>
          </header>

          <table className="report-meta">
            <tbody>
              <tr>
                <th>사건 번호</th>
                <td>
                  #{String(active.id).padStart(
                    4,
                    "0",
                  )}
                </td>
                <th>작성일</th>
                <td>
                  {formatDate(active.created_at)}
                </td>
              </tr>

              <tr>
                <th>상담 제목</th>
                <td>{active.title}</td>
                <th>최종 수정일</th>
                <td>
                  {formatDate(active.updated_at)}
                </td>
              </tr>

              <tr>
                <th>사건 분류</th>
                <td>{assessment.category}</td>
                <th>위험도</th>
                <td>
                  {riskLabel[assessment.level]}
                  {" "}
                  ({assessment.score} / 100)
                </td>
              </tr>
            </tbody>
          </table>

          <section className="report-section">
            <h2>평가 근거</h2>
            <p>{assessment.rationale}</p>
          </section>

          <section className="report-section">
            <h2>근거 법령</h2>

            {assessment.based_law.length ? (
              <ul>
                {assessment.based_law.map(
                  (law) => (
                    <li key={law}>
                      {law}
                    </li>
                  ),
                )}
              </ul>
            ) : (
              <p className="report-muted">
                확인된 근거 법령이 없습니다.
              </p>
            )}
          </section>

          <section className="report-section">
            <h2>권장 대응 조치</h2>

            {assessment.actions.length ? (
              <ol>
                {assessment.actions.map(
                  (action) => (
                    <li key={action}>
                      {action}
                    </li>
                  ),
                )}
              </ol>
            ) : (
              <p className="report-muted">
                권장 조치가 없습니다.
              </p>
            )}
          </section>

          <section className="report-section">
            <h2>상담 기록</h2>

            {messages.map((message, index) => (
              <div
                className="report-msg"
                key={message.id ?? index}
              >
                <b>
                  {message.role === "assistant"
                    ? "디딤"
                    : "상담자"}
                </b>

                <span>{message.content}</span>
              </div>
            ))}
          </section>

          <section className="report-section">
            <h2>첨부 증거 자료</h2>

            {attachments.length ? (
              <ul>
                {attachments.map(
                  (attachment) => (
                    <li key={attachment.id}>
                      {attachment.filename}
                      {" "}
                      ({formatBytes(attachment.size)},
                      {" "}
                      {formatDate(
                        attachment.created_at,
                      )})
                    </li>
                  ),
                )}
              </ul>
            ) : (
              <p className="report-muted">
                첨부된 파일이 없습니다.
              </p>
            )}
          </section>

          <footer className="report-footer">
            <p>
              본 보고서는 입력된 상담 내용을 바탕으로
              자동 생성된 참고 자료이며, 법률적·행정적
              최종 판단이 아닙니다.
              <br />
              정확한 처리를 위해 학교 관리자 및
              교원단체·법률 전문가의 검토를
              받으시기 바랍니다.
            </p>

            <div className="report-signature">
              <div>
                <span>작성자 확인</span>
                <i />
              </div>

              <div>
                <span>관리자 확인</span>
                <i />
              </div>
            </div>
          </footer>
        </section>
      )}
    </main>
  );
}


export default function App() {
  const [user, setUser] =
    useState<AuthUser | null>(null);

  const [checkingSession, setCheckingSession] =
    useState(true);


  useEffect(() => {
    let mounted = true;

    async function checkSession() {
      try {
        const currentUser =
          await getCurrentUser();

        if (mounted) {
          setUser(currentUser);
        }
      } catch (caughtError) {
        if (
          caughtError instanceof ApiError
          && caughtError.status !== 401
        ) {
          console.error(
            "세션 확인 실패:",
            caughtError,
          );
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
          디
        </div>

        <p>
          로그인 상태를 확인하고 있습니다…
        </p>
      </main>
    );
  }


  if (!user) {
    return (
      <LoginPage
        onLoggedIn={(loggedInUser) => {
          setUser(loggedInUser);
        }}
      />
    );
  }


  return (
    <Workspace
      user={user}
      onLoggedOut={() => {
        setUser(null);
      }}
    />
  );
}