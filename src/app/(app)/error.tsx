"use client"; // 에러 경계는 클라이언트 컴포넌트여야 한다

import Link from "next/link";
import { useEffect } from "react";
import { AppHeader } from "@/components/AppHeader";
import { PRIMARY_BUTTON, SECONDARY_BUTTON } from "@/components/states/CenteredState";
import { ErrorState } from "@/components/states/ErrorState";

/**
 * 제품 화면(app 그룹) 어디서든 예상 못 한 오류가 나면 여기로 온다. 시안 08과 같은 모양.
 * 무엇이 남아 있는지 먼저 말한다 — 01 입력은 이 브라우저에 자동 저장되어 있다.
 * Next 16 의 error.tsx 는 reset 대신 retry 를 받는다 (node_modules/next/dist/docs 참고).
 */
export default function AppError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <>
      <AppHeader />
      <ErrorState
        title="화면을 불러오지 못했어요"
        description="잠깐 문제가 생겼어요. 적어둔 아이디어는 이 브라우저에 자동 저장되어 있어서 그대로 남아 있어요."
        actions={
          <>
            <button type="button" className={PRIMARY_BUTTON} onClick={() => retry()}>
              다시 시도
            </button>
            <Link href="/new" className={SECONDARY_BUTTON}>
              아이디어로 돌아가기
            </Link>
          </>
        }
      />
    </>
  );
}
