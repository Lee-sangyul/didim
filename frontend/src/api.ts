import type { Assessment, Attachment, CaseItem, Message } from "./types";
const json = { "Content-Type": "application/json" };

export async function listCases(): Promise<CaseItem[]> { const r = await fetch("/api/cases"); if (!r.ok) throw Error("상담 목록을 불러오지 못했습니다."); return r.json(); }
export async function createCase(): Promise<CaseItem> { const r = await fetch("/api/cases", { method: "POST", headers: json, body: JSON.stringify({ title: "새 상담" }) }); return r.json(); }
export async function getMessages(id: number): Promise<Message[]> { const r = await fetch(`/api/cases/${id}/messages`); return r.json(); }
export async function removeCase(id: number): Promise<void> { await fetch(`/api/cases/${id}`, { method: "DELETE" }); }

export async function listAttachments(caseId: number): Promise<Attachment[]> { const r = await fetch(`/api/cases/${caseId}/attachments`); if (!r.ok) throw Error("첨부 파일 목록을 불러오지 못했습니다."); return r.json(); }
export async function uploadAttachment(caseId: number, file: File): Promise<Attachment> {
  const form = new FormData(); form.append("file", file);
  const r = await fetch(`/api/cases/${caseId}/attachments`, { method: "POST", body: form });
  if (!r.ok) throw Error("파일 업로드에 실패했습니다.");
  return r.json();
}
export async function removeAttachment(caseId: number, attachmentId: number): Promise<void> { await fetch(`/api/cases/${caseId}/attachments/${attachmentId}`, { method: "DELETE" }); }
export function attachmentDownloadUrl(caseId: number, attachmentId: number): string { return `/api/cases/${caseId}/attachments/${attachmentId}/download`; }

export interface AssessmentRecord { id: number; case_id: number; message_id: number | null; risk_level: string; risk_score: number; category: string; rationale: string; based_law: string[]; actions: string[]; created_at: string }
export async function getLatestAssessment(caseId: number): Promise<AssessmentRecord | null> {
  const r = await fetch(`/api/cases/${caseId}/assessments`);
  if (!r.ok) return null;
  const list: AssessmentRecord[] = await r.json();
  return list.length ? list[list.length - 1] : null;
}

export async function streamChat(id: number, content: string, onDelta: (text: string) => void): Promise<Assessment> {
  const r = await fetch(`/api/cases/${id}/chat`, { method: "POST", headers: json, body: JSON.stringify({ content }) });
  if (!r.ok || !r.body) throw Error("상담 요청에 실패했습니다.");
  const reader = r.body.getReader(), decoder = new TextDecoder(); let buffer = "", assessment: Assessment | undefined;
  while (true) { const { done, value } = await reader.read(); if (done) break; buffer += decoder.decode(value, { stream: true }); const events = buffer.split("\n\n"); buffer = events.pop() ?? ""; for (const raw of events) { const line = raw.split("\n").find(x => x.startsWith("data: ")); if (!line) continue; const data = JSON.parse(line.slice(6)); if (data.type === "delta") onDelta(data.text); if (data.type === "done") assessment = data.assessment; if (data.type === "error") throw Error(data.message); } }
  if (!assessment) throw Error("분석 결과가 없습니다."); return assessment;
}

