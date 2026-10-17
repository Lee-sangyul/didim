// 상담 화면의 "데이터와 동작" 전부: 상담 목록·메시지·평가·첨부를 서버에서 읽고,
// 전송·다시 생성·삭제·업로드·로그아웃을 수행한다. 화면 모양(레이아웃·다크 모드 등)은 모른다.
//
// 읽는 순서: ① 상태 선언 → ② 오류 처리 → ③ 데이터 읽기(refresh) → ④ 사용자 동작(addCase … handleLogout)
// 새 서버 동작을 추가할 때는 여기에 함수를 만들고, 맨 아래 return에 넣어 Workspace.tsx에서 꺼내 쓴다.
import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

import {
  ApiError,
  createCase,
  getLatestAssessment,
  getMessages,
  listAttachments,
  listCases,
  logout,
  removeAttachment,
  removeCase,
  streamChat,
  streamRegenerate,
  uploadAttachment,
} from "../../api";
import type { Assessment, Attachment, CaseItem, Message, RiskLevel } from "../../types";
import { emptyTitles, getRandomEmptyTitle, initialAssessment } from "../constants";

interface Options {
  /** 로그인이 풀렸을 때(401) 또는 로그아웃이 끝났을 때 */
  onLoggedOut: () => void;
}

export function useWorkspace({ onLoggedOut }: Options) {
  // ---------- 상태 ----------
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [assessment, setAssessment] = useState<Assessment>(initialAssessment);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [emptyTitle, setEmptyTitle] = useState(getRandomEmptyTitle);
  const [responseTime, setResponseTime] = useState<number | null>(null);
  // 보고 있는 답변 버전(메시지 id -> 인덱스). 없으면 최신 버전. 버전 자체는 서버(Message.versions)에 저장된다.
  const [activeVersions, setActiveVersions] = useState<Record<number, number>>({});
  // 다시 생성 중인 답변(스트리밍 텍스트). 완료되면 서버 값으로 대체된다.
  const [regenerating, setRegenerating] = useState<{ id: number; text: string } | null>(null);
  // 사용자가 스레드 맨 아래를 보고 있는지. 동작이 시작될 때 true로 바꿔 새 답변을 따라가게 한다.
  // (실제 스크롤은 useThreadScroll이 이 ref를 읽어서 한다)
  const stickToBottom = useRef(true);

  const active = cases.find(c => c.id === selected);
  const isGreetingOnly = messages.length === 1 && messages[0].role === "assistant";
  const visibleMessages = isGreetingOnly ? [] : messages;

  // ---------- 오류 처리 ----------
  function handleApiError(caughtError: unknown) {
    if (caughtError instanceof ApiError && caughtError.status === 401) {
      onLoggedOut();
      return;
    }

    if (caughtError instanceof Error) {
      setError(caughtError.message);
      return;
    }

    setError("요청을 처리하는 중 오류가 발생했습니다.");
  }

  // 잠깐 보여주고 사라지는 안내. 그 사이 다른 오류가 뜨면 그 오류는 지우지 않음
  function flashMessage(message: string) {
    setError(message);
    setTimeout(() => setError(current => (current === message ? "" : current)), 1500);
  }

  // ---------- 데이터 읽기 ----------
  async function loadAttachments(id: number) {
    try {
      setAttachments(await listAttachments(id));
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        onLoggedOut();
        return;
      }

      setAttachments([]);
    }
  }

  async function loadAssessment(id: number, fallback?: CaseItem) {
    const latest = await getLatestAssessment(id);

    if (latest) {
      setAssessment({
        level: latest.risk_level as RiskLevel,
        score: latest.risk_score,
        category: latest.category,
        rationale: latest.rationale,
        actions: latest.actions,
        based_law: latest.based_law,
        citations: latest.citations ?? []
      });
    } else if (fallback) {
      setAssessment({
        ...initialAssessment,
        level: fallback.risk_level,
        score: fallback.risk_score,
        category: fallback.category,
        based_law: fallback.based_law
      });
    } else {
      setAssessment(initialAssessment);
    }
  }

  // 서버의 상담 목록을 다시 읽고, 선택된 상담의 메시지·평가·첨부까지 맞춘다.
  async function refresh(prefer?: number) {
    const allCases = await listCases();
    setCases(allCases);

    // selected는 클로저 값이라 방금 삭제한 상담 id일 수 있으므로 목록에 있는지 확인
    const candidate = prefer ?? selected;
    const id = candidate != null && allCases.some(c => c.id === candidate)
      ? candidate
      : allCases[0]?.id;

    if (id == null) {
      setSelected(null);
      setMessages([]);
      setAttachments([]);
      setAssessment(initialAssessment);
      return;
    }

    setSelected(id);

    const [loadedMessages] = await Promise.all([
      getMessages(id),
      loadAssessment(id, allCases.find(c => c.id === id)),
      loadAttachments(id),
    ]);

    setMessages(loadedMessages);
  }

  useEffect(() => {
    refresh().catch(handleApiError);
  }, []);

  // ---------- 사용자 동작: 상담 ----------
  // 성공하면 true (화면 쪽에서 목록 패널을 닫는 데 쓴다)
  async function addCase(): Promise<boolean> {
    try {
      setError("");
      const createdCase = await createCase();
      setEmptyTitle(current => {
        const candidates = emptyTitles.filter(title => title !== current);
        return candidates[Math.floor(Math.random() * candidates.length)];
      });
      setAssessment(initialAssessment);
      setAttachments([]);
      setResponseTime(null);
      stickToBottom.current = true;
      await refresh(createdCase.id);
      return true;
    } catch (caughtError) {
      handleApiError(caughtError);
      return false;
    }
  }

  async function choose(id: number): Promise<boolean> {
    try {
      setError("");
      setSelected(id);
      setResponseTime(null);
      stickToBottom.current = true;

      const [loadedMessages] = await Promise.all([
        getMessages(id),
        loadAssessment(id, cases.find(c => c.id === id)),
        loadAttachments(id),
      ]);

      setMessages(loadedMessages);
      return true;
    } catch (caughtError) {
      handleApiError(caughtError);
      return false;
    }
  }

  async function deleteCase() {
    if (!selected || !confirm("이 상담 기록을 삭제할까요?")) return;

    try {
      setError("");
      await removeCase(selected);
      setSelected(null);
      setMessages([]);
      setAttachments([]);
      setAssessment(initialAssessment);
      setResponseTime(null);
      await refresh();
    } catch (caughtError) {
      handleApiError(caughtError);
    }
  }

  // ---------- 사용자 동작: 메시지 ----------
  async function send(e?: FormEvent, forcedContent?: string) {
    e?.preventDefault();

    const content = (forcedContent ?? input).trim();
    if (!content || loading) return;

    // 상담 생성 중에도 중복 전송되지 않도록 먼저 잠금
    setError("");
    setLoading(true);
    let placeholderAdded = false;

    try {
      let id = selected;
      if (!id) {
        const createdCase = await createCase();
        id = createdCase.id;
        setSelected(id);
      }
      const caseId = id;

      setInput("");
      stickToBottom.current = true;
      const startTime = performance.now();

      setMessages(m => [
        ...m,
        { case_id: caseId, role: "user", content },
        { case_id: caseId, role: "assistant", content: "" }
      ]);
      placeholderAdded = true;

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
      // 여기부터는 답변이 완성됐으므로 이후 오류가 나도 답변을 지우지 않음
      placeholderAdded = false;

      setAssessment(result);
      setResponseTime(Number(((performance.now() - startTime) / 1000).toFixed(1)));
      await refresh(caseId);
    } catch (caughtError) {
      if (placeholderAdded) {
        setMessages(m => m.slice(0, -1));
      }
      handleApiError(caughtError);
    } finally {
      setLoading(false);
    }
  }

  // 마지막 답변만 다시 생성한다. 서버가 같은 답변 메시지에 새 버전을 누적한다(사용자 메시지는 늘지 않음).
  async function regenerateAnswer(assistantMessage: Message) {
    const msgId = assistantMessage.id;
    if (!selected || loading || msgId == null) return;

    setLoading(true);
    setError("");
    setRegenerating({ id: msgId, text: "" });
    stickToBottom.current = true;
    const startTime = performance.now();

    try {
      const newAssessment = await streamRegenerate(selected, msgId, (deltaText) => {
        setRegenerating(prev => (prev ? { ...prev, text: prev.text + deltaText } : prev));
      });

      setAssessment(newAssessment);
      setResponseTime(Number(((performance.now() - startTime) / 1000).toFixed(1)));
      // 서버가 저장한 버전 목록으로 동기화하고, 새 버전(마지막)을 보여 준다
      setActiveVersions(prev => {
        const { [msgId]: _drop, ...rest } = prev;
        return rest;
      });
      await refresh(selected);
    } catch (err) {
      handleApiError(err); // 실패하면 서버에 아무것도 저장되지 않으므로 기존 답변이 그대로 남는다
    } finally {
      setRegenerating(null);
      setLoading(false);
    }
  }

  // 이전/다음 버전으로 이동 (count = 그 답변의 전체 버전 수)
  function changeVersion(msgId: number, delta: number, count: number) {
    setActiveVersions(prev => {
      const current = prev[msgId] ?? count - 1; // 선택한 적이 없으면 최신 버전
      return { ...prev, [msgId]: Math.max(0, Math.min(count - 1, current + delta)) };
    });
  }

  // ---------- 사용자 동작: 첨부 ----------
  async function onUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    setUploading(true);
    setError("");

    try {
      let id = selected;
      if (!id) {
        const createdCase = await createCase();
        id = createdCase.id;
        setSelected(id);
        await refresh(id);
      }

      await uploadAttachment(id, file);
      await loadAttachments(id);
    } catch (caughtError) {
      handleApiError(caughtError);
    } finally {
      setUploading(false);
    }
  }

  async function onDeleteAttachment(attachmentId: number) {
    if (!selected) return;

    try {
      setError("");
      await removeAttachment(selected, attachmentId);
      await loadAttachments(selected);
    } catch (caughtError) {
      handleApiError(caughtError);
    }
  }

  // ---------- 사용자 동작: 로그아웃 ----------
  async function handleLogout() {
    if (loggingOut) return;

    setLoggingOut(true);
    setError("");

    try {
      await logout();
    } catch (caughtError) {
      if (!(caughtError instanceof ApiError) || caughtError.status !== 401) {
        handleApiError(caughtError);
        setLoggingOut(false);
        return;
      }
    }

    onLoggedOut();
  }

  return {
    // 상태
    cases, selected, active, messages, visibleMessages, input, setInput, assessment,
    loading, error, setError, attachments, uploading, loggingOut, emptyTitle, responseTime,
    activeVersions, regenerating, stickToBottom,
    // 동작
    flashMessage, addCase, choose, deleteCase, send, regenerateAnswer, changeVersion,
    onUpload, onDeleteAttachment, handleLogout,
  };
}
