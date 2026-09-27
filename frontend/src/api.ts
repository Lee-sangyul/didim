import type {
  Assessment,
  Attachment,
  CaseItem,
  Message,
} from "./types";


export interface AuthUser {
  id: number;
  username: string;
  name: string;
  role: string;
  is_active: boolean;
}


export interface LoginResponse {
  message: string;
  user: AuthUser;
}


export interface LogoutResponse {
  message: string;
}


export interface AssessmentRecord {
  id: number;
  case_id: number;
  message_id: number | null;
  risk_level: string;
  risk_score: number;
  category: string;
  rationale: string;
  based_law: string[];
  actions: string[];
  created_at: string;
}


export class ApiError extends Error {
  status: number;

  constructor(
    message: string,
    status: number,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}


async function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const response = await fetch(
    input,
    {
      ...init,
      credentials: "include",
    },
  );

  if (!response.ok) {
    let message = "요청을 처리하지 못했습니다.";

    try {
      const data = await response.json();

      if (
        typeof data === "object"
        && data !== null
        && "detail" in data
        && typeof data.detail === "string"
      ) {
        message = data.detail;
      }
    } catch {
      // JSON 응답이 아니면 기본 오류 메시지를 사용한다.
    }

    throw new ApiError(
      message,
      response.status,
    );
  }

  return response;
}


export async function login(
  username: string,
  password: string,
): Promise<LoginResponse> {
  const response = await apiFetch(
    "/api/auth/login",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        password,
      }),
    },
  );

  return response.json();
}


export async function logout(): Promise<void> {
  await apiFetch(
    "/api/auth/logout",
    {
      method: "POST",
    },
  );
}


export async function getCurrentUser(): Promise<AuthUser> {
  const response = await apiFetch(
    "/api/auth/me",
  );

  return response.json();
}


export async function listCases(): Promise<CaseItem[]> {
  const response = await apiFetch(
    "/api/cases",
  );

  return response.json();
}


export async function createCase(): Promise<CaseItem> {
  const response = await apiFetch(
    "/api/cases",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title: "새 상담",
      }),
    },
  );

  return response.json();
}


export async function getMessages(
  id: number,
): Promise<Message[]> {
  const response = await apiFetch(
    `/api/cases/${id}/messages`,
  );

  return response.json();
}


export async function removeCase(
  id: number,
): Promise<void> {
  await apiFetch(
    `/api/cases/${id}`,
    {
      method: "DELETE",
    },
  );
}


export async function listAttachments(
  caseId: number,
): Promise<Attachment[]> {
  const response = await apiFetch(
    `/api/cases/${caseId}/attachments`,
  );

  return response.json();
}


export async function uploadAttachment(
  caseId: number,
  file: File,
): Promise<Attachment> {
  const formData = new FormData();

  formData.append(
    "file",
    file,
  );

  const response = await apiFetch(
    `/api/cases/${caseId}/attachments`,
    {
      method: "POST",
      body: formData,
    },
  );

  return response.json();
}


export async function removeAttachment(
  caseId: number,
  attachmentId: number,
): Promise<void> {
  await apiFetch(
    `/api/cases/${caseId}/attachments/${attachmentId}`,
    {
      method: "DELETE",
    },
  );
}


export function attachmentDownloadUrl(
  caseId: number,
  attachmentId: number,
): string {
  return (
    `/api/cases/${caseId}`
    + `/attachments/${attachmentId}/download`
  );
}


export async function getLatestAssessment(
  caseId: number,
): Promise<AssessmentRecord | null> {
  const response = await apiFetch(
    `/api/cases/${caseId}/assessments`,
  );

  const assessments: AssessmentRecord[] = (
    await response.json()
  );

  if (assessments.length === 0) {
    return null;
  }

  return assessments[
    assessments.length - 1
  ];
}


export async function streamChat(
  id: number,
  content: string,
  onDelta: (text: string) => void,
): Promise<Assessment> {
  const response = await apiFetch(
    `/api/cases/${id}/chat`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        content,
      }),
    },
  );

  if (!response.body) {
    throw new ApiError(
      "상담 응답을 읽을 수 없습니다.",
      response.status,
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  let buffer = "";
  let assessment: Assessment | undefined;

  while (true) {
    const {
      done,
      value,
    } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(
      value,
      {
        stream: true,
      },
    );

    const events = buffer.split("\n\n");

    buffer = events.pop() ?? "";

    for (const rawEvent of events) {
      const dataLine = rawEvent
        .split("\n")
        .find(
          (line) => line.startsWith("data: "),
        );

      if (!dataLine) {
        continue;
      }

      const data = JSON.parse(
        dataLine.slice(6),
      );

      if (data.type === "delta") {
        onDelta(data.text);
      }

      if (data.type === "done") {
        assessment = data.assessment;
      }

      if (data.type === "error") {
        throw new Error(data.message);
      }
    }
  }

  if (!assessment) {
    throw new Error(
      "분석 결과가 없습니다.",
    );
  }

  return assessment;
}