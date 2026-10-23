/**
 * 로그인 무차별 대입 방지의 브라우저 쪽 절반.
 *
 * 서버(backend/app/services/login_guard.py)가 실제 차단을 맡는다. 이 모듈은 같은 한도를
 * 브라우저에서 미리 적용해 불필요한 요청을 막고, 남은 시도 횟수와 잠금 해제 시간을 보여 준다.
 * 브라우저 저장소는 사용자가 지울 수 있으므로 보안 장치가 아니라 편의 장치다.
 *
 * 아래 두 값은 서버의 MAX_FAILURES_PER_USER, WINDOW_MINUTES와 같아야 한다
 * (scripts/checks/regressions.py R019가 점검한다).
 */
// 이 장치는 빌드 시 VITE_LOGIN_GUARD=true일 때만 동작한다. 기본은 꺼짐(데모 시연 중 잠금 방지, 2026-10).
// 서버의 LOGIN_RATE_LIMIT_ENABLED와 같은 상태로 맞춘다.
export const LOGIN_GUARD_ENABLED = import.meta.env.VITE_LOGIN_GUARD === "true";

export const MAX_FAILURES = 5;
export const WINDOW_MINUTES = 15;

const STORAGE_KEY = "didim.loginGuard";
const WINDOW_MS = WINDOW_MINUTES * 60 * 1000;

interface GuardState {
  failures: Record<string, number[]>; // 아이디 -> 실패 시각(ms)
  locks: Record<string, number>; // 아이디 -> 잠금 해제 시각(ms)
}

function key(username: string): string {
  return username.trim().toLowerCase();
}

function load(): GuardState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return { failures: parsed.failures ?? {}, locks: parsed.locks ?? {} };
    }
  } catch {
    // 저장소를 쓸 수 없거나 값이 깨졌으면 빈 상태로 시작한다
  }
  return { failures: {}, locks: {} };
}

function save(state: GuardState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // 저장 실패는 무시한다 (서버가 실제 차단을 한다)
  }
}

function prune(state: GuardState, now: number): void {
  for (const [name, times] of Object.entries(state.failures)) {
    const recent = times.filter((t) => now - t < WINDOW_MS);
    if (recent.length) state.failures[name] = recent;
    else delete state.failures[name];
  }
  for (const [name, until] of Object.entries(state.locks)) {
    if (until <= now) delete state.locks[name];
  }
}

/** 잠금이 풀릴 때까지 남은 밀리초. 잠겨 있지 않으면 0. */
export function lockRemainingMs(username: string, now = Date.now()): number {
  if (!LOGIN_GUARD_ENABLED) return 0;
  const state = load();
  prune(state, now);
  return Math.max(0, (state.locks[key(username)] ?? 0) - now);
}

/** 이 아이디로 더 시도할 수 있는 횟수. */
export function attemptsLeft(username: string, now = Date.now()): number {
  const state = load();
  prune(state, now);
  return Math.max(0, MAX_FAILURES - (state.failures[key(username)]?.length ?? 0));
}

/** 서버가 401을 돌려줬을 때 호출한다. 한도에 도달하면 잠금 해제 시각을 정한다. */
export function recordFailure(username: string, now = Date.now()): { left: number; lockedMs: number } {
  if (!LOGIN_GUARD_ENABLED) return { left: 0, lockedMs: 0 };
  const state = load();
  prune(state, now);
  const name = key(username);
  const times = [...(state.failures[name] ?? []), now];
  state.failures[name] = times;

  if (times.length >= MAX_FAILURES) {
    state.locks[name] = times[times.length - MAX_FAILURES] + WINDOW_MS;
  }

  save(state);
  return {
    left: Math.max(0, MAX_FAILURES - times.length),
    lockedMs: Math.max(0, (state.locks[name] ?? 0) - now),
  };
}

/** 서버가 429(잠금)를 돌려줬을 때 호출한다. */
export function recordServerLock(username: string, retryAfterSeconds: number, now = Date.now()): void {
  if (!LOGIN_GUARD_ENABLED) return;
  const state = load();
  prune(state, now);
  state.locks[key(username)] = now + retryAfterSeconds * 1000;
  save(state);
}

/** 로그인에 성공하면 호출한다. */
export function clearFailures(username: string): void {
  const state = load();
  const name = key(username);
  delete state.failures[name];
  delete state.locks[name];
  save(state);
}

export function formatCountdown(ms: number): string {
  const total = Math.ceil(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}분 ${String(s).padStart(2, "0")}초`;
}
