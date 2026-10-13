"use client";

import { useEffect, useState } from "react";

/**
 * 진행 단계를 일정 간격으로 하나씩 넘긴다. 마지막 단계에서 멈춘다.
 *
 * 실제 엔드포인트가 붙기 전, 상태 화면 미리보기(/states/*)에서 단계가 어떻게 넘어가는지
 * 보여주는 용도다. 실제 화면에서는 서버가 알려준 진행 단계를 그대로 넘긴다.
 */
export function useStepTicker(total: number, intervalMs = 2500, start = 0) {
  const [current, setCurrent] = useState(start);

  useEffect(() => {
    if (current >= total - 1) return;
    const timer = setTimeout(() => setCurrent((c) => c + 1), intervalMs);
    return () => clearTimeout(timer);
  }, [current, total, intervalMs]);

  return current;
}
