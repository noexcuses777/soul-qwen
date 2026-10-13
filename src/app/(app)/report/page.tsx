import type { Metadata } from "next";
import { ReportPageClient } from "./ReportPageClient";

export const metadata: Metadata = { title: "리포트" };

export default function Page() {
  return <ReportPageClient />;
}
