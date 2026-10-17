// 상담 화면에서 함께 쓰는 상수. 값만 바꿀 때는 이 파일만 고치면 된다.
import type { Assessment, RiskLevel } from "../types";

export const riskLabel: Record<RiskLevel, string> = {
  low: "낮음",
  caution: "주의",
  danger: "위험",
  emergency: "긴급",
};

export const initialAssessment: Assessment = {
  level: "low",
  score: 0,
  category: "분석 전",
  rationale: "상황을 입력하면 위험도와 대응 절차를 정리합니다.",
  actions: [],
  based_law: [],
};

export const emptyTitles = [
  "혼자 감당하지 않아도 됩니다",
  "무슨 생각을 하시나요?",
  "지금 겪고 있는 일을 들려주세요",
  "편하게 말씀해 주세요",
  "필요한 도움을 함께 찾아볼게요",
];

export function getRandomEmptyTitle() {
  return emptyTitles[Math.floor(Math.random() * emptyTitles.length)];
}

// 입력창이 늘어나는 최대 줄 수. 넘으면 스크롤된다.
export const TEXTAREA_MAX_LINES = 5;

// 전송 가능한 최소 글자 수. 백엔드 ChatInput.min_length와 같아야 한다(scripts R009가 점검).
export const MIN_MESSAGE_LENGTH = 1;

// 좌우 패널 기본 너비(px)
export const DEFAULT_RAIL_WIDTH = 248;
export const DEFAULT_ASIDE_WIDTH = 332;

// 북마크를 브라우저에 저장하는 키
export const BOOKMARK_STORAGE_KEY = "didim-bookmarks";
