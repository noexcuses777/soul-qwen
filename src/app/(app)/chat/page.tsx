import type { Metadata } from "next";
import { ChatClient } from "./ChatClient";

export const metadata: Metadata = { title: "대화" };

/**
 * 시안: design/screens/04-chat.html · 04-1-chat-dm.html — 대화 영역만 스크롤되도록 화면 높이에 맞춘다.
 * ?ask= 로 들어오면(05 리포트 "이어서 물어볼 지점") 그 질문을 입력창에 채워 둔다.
 */
export default async function Page({ searchParams }: { searchParams: Promise<{ ask?: string; persona?: string }> }) {
  const { ask, persona } = await searchParams;
  return (
    <div className="flex h-dvh flex-col">
      <ChatClient initialDraft={ask?.slice(0, 500) ?? ""} initialPersona={persona ?? ""} />
    </div>
  );
}
