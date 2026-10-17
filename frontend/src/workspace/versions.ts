// 답변 다시 생성 기능의 "버전" 계산. 버전 자체는 서버(Message.versions)가 저장한다.
import type { Message } from "../types";

// 답변의 모든 버전(오래된 것부터). 서버가 versions를 비워 두면 버전이 하나뿐이다.
export function versionsOf(m: Message): string[] {
  return m.versions && m.versions.length > 0 ? m.versions : [m.content];
}
