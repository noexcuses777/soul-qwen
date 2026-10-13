import type { Metadata } from "next";
import { IBM_Plex_Sans_KR, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const plexSans = IBM_Plex_Sans_KR({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

// 라벨·숫자·수치 전용. eyebrow, STEP 번호, ROUND 표기, 통계에 쓴다.
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Soul — 첫 고객 인터뷰 전에, 리허설부터",
    template: "%s · Soul",
  },
  description:
    "아이디어를 적으면 타깃 후보를 찾아주고, 여러 페르소나가 한 방에서 서로 듣고 반박하며 대화합니다. 인터뷰를 대신하지 않고, 앞뒤를 채웁니다.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body className={`${plexSans.variable} ${plexMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
