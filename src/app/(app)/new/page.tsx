import type { Metadata } from "next";
import { IdeaFormClient } from "./IdeaFormClient";

export const metadata: Metadata = { title: "아이디어 입력" };

/** 시안: design/screens/01-idea-input.html */
export default function Page() {
  return <IdeaFormClient />;
}
