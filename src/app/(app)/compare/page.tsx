import type { Metadata } from "next";
import { AppHeader } from "@/components/AppHeader";
import { CompareClient } from "./CompareClient";

export const metadata: Metadata = { title: "한눈에 보기" };

/** 시안: design/screens/03-compare.html */
export default function Page() {
  return (
    <>
      <AppHeader current="03" />
      <CompareClient />
    </>
  );
}
