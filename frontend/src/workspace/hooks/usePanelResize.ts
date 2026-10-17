// 왼쪽 "최근 상담" 목록과 오른쪽 "상담 결과" 패널의 너비 조절(마우스 드래그 + 키보드).
// 반환한 railResizerProps / asideResizerProps를 각 구분선(div)에 펼쳐서 쓴다.
import { KeyboardEvent, PointerEvent, useRef, useState } from "react";

import { DEFAULT_ASIDE_WIDTH, DEFAULT_RAIL_WIDTH } from "../constants";

const RAIL_MIN = 180;

const railMax = () => Math.min(420, Math.floor(window.innerWidth * 0.35));
const asideMax = () => Math.floor(window.innerWidth / 4);

export function usePanelResize() {
  const [asideWidth, setAsideWidth] = useState(DEFAULT_ASIDE_WIDTH);
  const [railWidth, setRailWidth] = useState(DEFAULT_RAIL_WIDTH);
  const resizingAside = useRef(false);
  const resizingRail = useRef(false);

  const resizeRail = (clientX: number) => {
    setRailWidth(Math.max(RAIL_MIN, Math.min(railMax(), clientX)));
  };

  const resizeAside = (clientX: number) => {
    const nextWidth = window.innerWidth - clientX;

    setAsideWidth(Math.max(0, Math.min(asideMax(), nextWidth)));
  };

  const railResizerProps = {
    role: "separator",
    "aria-orientation": "vertical" as const,
    "aria-label": "최근 상담 목록 너비 조절",
    title: "드래그하여 최근 상담 목록 너비 조절",
    tabIndex: 0,
    onKeyDown: (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "ArrowLeft") setRailWidth(width => Math.max(RAIL_MIN, width - 16));
      if (e.key === "ArrowRight") setRailWidth(width => Math.min(railMax(), width + 16));
      if (e.key === "Home") setRailWidth(RAIL_MIN);
      if (e.key === "End") setRailWidth(railMax());
    },
    onPointerDown: (e: PointerEvent<HTMLDivElement>) => {
      if (e.button !== 0 || window.innerWidth <= 700) return;
      resizingRail.current = true;
      e.currentTarget.setPointerCapture(e.pointerId);
      e.preventDefault();
    },
    onPointerMove: (e: PointerEvent<HTMLDivElement>) => {
      if (resizingRail.current) resizeRail(e.clientX);
    },
    onPointerUp: (e: PointerEvent<HTMLDivElement>) => {
      resizingRail.current = false;
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
    },
    onPointerCancel: () => {
      resizingRail.current = false;
    },
  };

  const asideResizerProps = {
    role: "separator",
    "aria-orientation": "vertical" as const,
    "aria-label": "상담 결과창 너비 조절",
    title: "드래그하여 너비 조절",
    tabIndex: 0,
    onKeyDown: (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "ArrowLeft") setAsideWidth(width => Math.min(asideMax(), width + 16));
      if (e.key === "ArrowRight") setAsideWidth(width => Math.max(0, width - 16));
      if (e.key === "Home") setAsideWidth(0);
      if (e.key === "End") setAsideWidth(asideMax());
    },
    onPointerDown: (e: PointerEvent<HTMLDivElement>) => {
      if (e.button !== 0) return;
      resizingAside.current = true;
      e.currentTarget.setPointerCapture(e.pointerId);
      e.preventDefault();
    },
    onPointerMove: (e: PointerEvent<HTMLDivElement>) => {
      if (resizingAside.current) resizeAside(e.clientX);
    },
    onPointerUp: (e: PointerEvent<HTMLDivElement>) => {
      resizingAside.current = false;
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
    },
    onPointerCancel: () => {
      resizingAside.current = false;
    },
  };

  return { asideWidth, setAsideWidth, railWidth, railResizerProps, asideResizerProps };
}
