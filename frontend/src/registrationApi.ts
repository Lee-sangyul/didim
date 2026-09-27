export type RegistrationStatus =
  | "pending"
  | "approved"
  | "rejected";


export interface RegistrationDocument {
  id: number;
  original_filename: string;
  content_type: string;
  size: number;
  sha256: string;
  created_at: string;
  deleted_at: string | null;
}


export interface RegistrationApplication {
  id: number;
  username: string;
  name: string;
  school_name: string;
  email: string;
  phone: string | null;
  status: RegistrationStatus;
  rejection_reason: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
  document_delete_after: string | null;
  created_at: string;
  updated_at: string;
  document: RegistrationDocument | null;
}


export interface CreateRegistrationInput {
  username: string;
  password: string;
  name: string;
  schoolName: string;
  email: string;
  phone: string;
  document: File;
}


export interface CreateRegistrationResponse {
  message: string;
  application_id: number;
  status: RegistrationStatus;
  notice: string;
}


export interface ApproveRegistrationResponse {
  message: string;
  application_id: number;
  status: RegistrationStatus;
  user: {
    id: number;
    username: string;
    name: string;
    role: string;
    is_active: boolean;
  };
}


export interface RejectRegistrationResponse {
  message: string;
  application_id: number;
  status: RegistrationStatus;
  rejection_reason: string;
}


export class RegistrationApiError extends Error {
  status: number;

  constructor(
    message: string,
    status: number,
  ) {
    super(message);

    this.name = "RegistrationApiError";
    this.status = status;
  }
}


async function registrationFetch(
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
      const data: unknown = await response.json();

      if (
        typeof data === "object"
        && data !== null
        && "detail" in data
        && typeof data.detail === "string"
      ) {
        message = data.detail;
      }
    } catch {
      // JSON 오류 응답이 아니면 기본 메시지를 사용한다.
    }

    throw new RegistrationApiError(
      message,
      response.status,
    );
  }

  return response;
}


export async function createRegistrationApplication(
  input: CreateRegistrationInput,
): Promise<CreateRegistrationResponse> {
  const formData = new FormData();

  formData.append(
    "username",
    input.username,
  );

  formData.append(
    "password",
    input.password,
  );

  formData.append(
    "name",
    input.name,
  );

  formData.append(
    "school_name",
    input.schoolName,
  );

  formData.append(
    "email",
    input.email,
  );

  if (input.phone.trim()) {
    formData.append(
      "phone",
      input.phone,
    );
  }

  formData.append(
    "document",
    input.document,
  );

  const response = await registrationFetch(
    "/api/registration/applications",
    {
      method: "POST",
      body: formData,
    },
  );

  return response.json();
}


export async function listRegistrationApplications(
  status?: RegistrationStatus,
): Promise<RegistrationApplication[]> {
  const query = status
    ? `?application_status=${encodeURIComponent(status)}`
    : "";

  const response = await registrationFetch(
    `/api/admin/registration-applications${query}`,
  );

  return response.json();
}


export async function approveRegistrationApplication(
  applicationId: number,
): Promise<ApproveRegistrationResponse> {
  const response = await registrationFetch(
    (
      "/api/admin/registration-applications/"
      + `${applicationId}/approve`
    ),
    {
      method: "POST",
    },
  );

  return response.json();
}


export async function rejectRegistrationApplication(
  applicationId: number,
  reason: string,
): Promise<RejectRegistrationResponse> {
  const response = await registrationFetch(
    (
      "/api/admin/registration-applications/"
      + `${applicationId}/reject`
    ),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        reason,
      }),
    },
  );

  return response.json();
}