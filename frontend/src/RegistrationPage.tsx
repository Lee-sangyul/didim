import {
  useState,
  type FormEvent,
} from "react";

import {
  createRegistrationApplication,
  RegistrationApiError,
} from "./registrationApi";


interface RegistrationPageProps {
  onBack: () => void;
}


export default function RegistrationPage({
  onBack,
}: RegistrationPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = (
    useState("")
  );
  const [name, setName] = useState("");
  const [schoolName, setSchoolName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [document, setDocument] = (
    useState<File | null>(null)
  );

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = (
    useState("")
  );

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setError("");
    setSuccessMessage("");

    if (password !== passwordConfirm) {
      setError(
        "비밀번호 확인이 일치하지 않습니다.",
      );

      return;
    }

    if (!document) {
      setError(
        "교직원 확인 문서를 선택해 주세요.",
      );

      return;
    }

    const allowedTypes = new Set([
      "application/pdf",
      "image/jpeg",
      "image/png",
    ]);

    if (!allowedTypes.has(document.type)) {
      setError(
        "PDF, JPG, PNG 파일만 제출할 수 있습니다.",
      );

      return;
    }

    if (document.size > 10 * 1024 * 1024) {
      setError(
        "문서 크기는 최대 10MB입니다.",
      );

      return;
    }

    setLoading(true);

    try {
      const result = (
        await createRegistrationApplication({
          username: username.trim(),
          password,
          name: name.trim(),
          schoolName: schoolName.trim(),
          email: email.trim(),
          phone: phone.trim(),
          document,
        })
      );

      setSuccessMessage(result.message);

    } catch (caughtError) {
      if (
        caughtError
        instanceof RegistrationApiError
      ) {
        setError(caughtError.message);
      } else {
        setError(
          "계정 발급 신청 중 오류가 발생했습니다.",
        );
      }

    } finally {
      setLoading(false);
    }
  }

  if (successMessage) {
    return (
      <main className="registration-page">
        <section className="registration-result">
          <div className="registration-result-icon">
            ✓
          </div>

          <span className="registration-eyebrow">
            신청 완료
          </span>

          <h1>계정 발급 신청을 접수했습니다.</h1>

          <p>{successMessage}</p>

          <div className="registration-notice">
            <strong>안내</strong>

            <p>
              제출 문서는 관리자 확인 목적으로만
              사용됩니다. 현재 버전에서는 문서의
              진위 여부를 자동으로 확인하지 않습니다.
            </p>
          </div>

          <button
            type="button"
            className="registration-primary-button"
            onClick={onBack}
          >
            로그인 화면으로 돌아가기
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="registration-page">
      <section className="registration-card">
        <header className="registration-header">
          <button
            type="button"
            className="registration-back-button"
            onClick={onBack}
            disabled={loading}
            aria-label="로그인 화면으로 돌아가기"
          >
            ←
          </button>

          <div>
            <span className="registration-eyebrow">
              DIDIM ACCOUNT
            </span>

            <h1>교직원 계정 신청</h1>

            <p>
              신청 정보와 교직원 확인 문서를 제출하면
              관리자가 검토한 뒤 계정을 발급합니다.
            </p>
          </div>
        </header>

        <form
          className="registration-form"
          onSubmit={handleSubmit}
        >
          <div className="registration-section">
            <div className="registration-section-heading">
              <span>1</span>

              <div>
                <h2>로그인 정보</h2>
                <p>사용할 아이디와 비밀번호를 입력하세요.</p>
              </div>
            </div>

            <div className="registration-grid">
              <label>
                <span>아이디</span>

                <input
                  type="text"
                  value={username}
                  onChange={(event) => {
                    setUsername(event.target.value);
                  }}
                  minLength={3}
                  maxLength={50}
                  pattern="[A-Za-z0-9_]+"
                  autoComplete="username"
                  disabled={loading}
                  required
                />

                <small>
                  영문, 숫자, 밑줄을 사용할 수 있습니다.
                </small>
              </label>

              <div className="registration-grid-spacer" />

              <label>
                <span>비밀번호</span>

                <input
                  type="password"
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                  }}
                  minLength={8}
                  maxLength={256}
                  autoComplete="new-password"
                  disabled={loading}
                  required
                />
              </label>

              <label>
                <span>비밀번호 확인</span>

                <input
                  type="password"
                  value={passwordConfirm}
                  onChange={(event) => {
                    setPasswordConfirm(
                      event.target.value,
                    );
                  }}
                  minLength={8}
                  maxLength={256}
                  autoComplete="new-password"
                  disabled={loading}
                  required
                />
              </label>
            </div>
          </div>

          <div className="registration-section">
            <div className="registration-section-heading">
              <span>2</span>

              <div>
                <h2>교직원 정보</h2>
                <p>관리자가 신청자를 확인할 정보입니다.</p>
              </div>
            </div>

            <div className="registration-grid">
              <label>
                <span>이름</span>

                <input
                  type="text"
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value);
                  }}
                  maxLength={100}
                  autoComplete="name"
                  disabled={loading}
                  required
                />
              </label>

              <label>
                <span>학교명</span>

                <input
                  type="text"
                  value={schoolName}
                  onChange={(event) => {
                    setSchoolName(
                      event.target.value,
                    );
                  }}
                  maxLength={200}
                  disabled={loading}
                  required
                />
              </label>

              <label>
                <span>이메일</span>

                <input
                  type="email"
                  value={email}
                  onChange={(event) => {
                    setEmail(event.target.value);
                  }}
                  maxLength={255}
                  autoComplete="email"
                  disabled={loading}
                  required
                />
              </label>

              <label>
                <span>전화번호 · 선택</span>

                <input
                  type="tel"
                  value={phone}
                  onChange={(event) => {
                    setPhone(event.target.value);
                  }}
                  maxLength={30}
                  autoComplete="tel"
                  disabled={loading}
                />
              </label>
            </div>
          </div>

          <div className="registration-section">
            <div className="registration-section-heading">
              <span>3</span>

              <div>
                <h2>확인 문서</h2>

                <p>
                  재직증명서 등 교직원임을 확인할
                  문서를 제출하세요.
                </p>
              </div>
            </div>

            <label className="registration-file-field">
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={(event) => {
                  const selectedFile = (
                    event.target.files?.[0]
                    ?? null
                  );

                  setDocument(selectedFile);
                }}
                disabled={loading}
                required
              />

              <span className="registration-file-icon">
                📄
              </span>

              <strong>
                {document
                  ? document.name
                  : "문서를 선택하세요"}
              </strong>

              <small>
                PDF, JPG, PNG · 최대 10MB
              </small>
            </label>

            <div className="registration-document-warning">
              <strong>문서 제출 안내</strong>

              <p>
                제출 문서는 관리자 검토에 사용됩니다.
                현재 버전은 문서의 진위를 자동으로
                확인하지 않으며, 승인 여부는 관리자가
                직접 결정합니다.
              </p>
            </div>
          </div>

          {error && (
            <div
              className="registration-error"
              role="alert"
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            className="registration-primary-button"
            disabled={loading}
          >
            {loading
              ? "신청서를 제출하는 중…"
              : "계정 발급 신청"}
          </button>
        </form>
      </section>
    </main>
  );
}