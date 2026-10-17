// 왼쪽 "최근 상담" 목록. 상담을 고르거나 새로 시작한다.
import type { CaseItem } from "../../types";

interface Props {
  cases: CaseItem[];
  selected: number | null;
  open: boolean; // 좁은 화면에서 목록이 펼쳐진 상태
  onAddCase: () => void;
  onChoose: (id: number) => void;
}

export default function CaseRail({ cases, selected, open, onAddCase, onChoose }: Props) {
  return (
    <nav className={`rail ${open ? "open" : ""}`}>
      <div className="brand">
        <div className="logo">
          <img src="/icons/icon.svg" alt="디딤" />
        </div>
        <div>
          <b>디딤</b>
          <small>교권 침해 상담</small>
        </div>
      </div>
      <button className="new" onClick={onAddCase}>＋ 새 상담 시작</button>
      <div className="rail-label">최근 상담</div>
      <div className="case-list">
        {cases.map((caseItem) => (
          <button
            className={
              `case ${selected === caseItem.id
                ? "active"
                : ""
              }`
            }
            onClick={() => onChoose(caseItem.id)}
            key={caseItem.id}
          >
            <i className={caseItem.risk_level} />

            <span>
              <b>{caseItem.title}</b>
              <small>{caseItem.category} · {caseItem.risk_score}점</small>
            </span>
          </button>
        ))}
      </div>

      <div className="privacy">
        🔒 상담은 사용자별로 분리되어 저장됩니다.
      </div>
    </nav>
  );
}
