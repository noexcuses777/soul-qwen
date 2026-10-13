import type { Metadata } from "next";
import Link from "next/link";
import { AppHeader, Logo } from "@/components/AppHeader";
import { CenteredState, PRIMARY_BUTTON } from "@/components/states/CenteredState";

export const metadata: Metadata = { title: "아이디어 없음" };

/** 첫 화면에서 흐름 전체를 보여준다. 처음 온 사람이 무엇을 하게 될지 알고 시작하도록. */
const FLOW = [
  { no: "01", title: "아이디어 적기", body: "한 줄이면 충분해요" },
  { no: "02", title: "타깃 고르기", body: "추천 후보 중 최대 3개를 골라요" },
  { no: "03", title: "함께 이야기", body: "선택한 페르소나가 서로 듣고 답해요" },
  { no: "04", title: "리포트 받기", body: "쟁점과 다음 질문이 나와요" },
];

/** 시안: design/screens/06-empty.html — 적어둔 아이디어가 하나도 없을 때 */
export default function Page() {
  return (
    <>
      <AppHeader current="01" />
      <CenteredState
        icon={<Logo size={72} muted />}
        title="아직 적어둔 아이디어가 없어요"
        description="아이디어를 적으면 관련 이용자 후보를 찾아드려요."
        actions={
          <Link href="/new" className={PRIMARY_BUTTON}>
            아이디어 적기
          </Link>
        }
      >
        <ol className="mt-3 flex overflow-hidden rounded-card border border-card bg-base">
          {FLOW.map((step, i) => (
            <li
              key={step.no}
              className={`flex w-60 flex-col gap-[7px] px-[22px] py-5 ${i > 0 ? "border-l border-divider" : ""}`}
            >
              <span className="font-mono text-[11px] font-semibold tracking-[0.12em] text-brand">{step.no}</span>
              <span className="text-sm font-semibold">{step.title}</span>
              <span className="text-[13px] leading-[1.6] text-muted">{step.body}</span>
            </li>
          ))}
        </ol>
      </CenteredState>
    </>
  );
}
