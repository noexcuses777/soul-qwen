import type { PersonaColor } from "@/lib/types";

const BG: Record<PersonaColor, string> = {
  1: "bg-persona-1",
  2: "bg-persona-2",
  3: "bg-persona-3",
  4: "bg-persona-4",
  5: "bg-persona-5",
};

const SIZE = {
  sm: "size-6",
  md: "size-8",
  lg: "size-[38px]",
} as const;

/** Decorative fictional faces, seeded by display identity; no age, gender or stance inference. */
export type AvatarFace = { id?: string };

export function PersonaAvatar({
  name,
  color,
  size = "md",
  face,
}: {
  name: string;
  color: PersonaColor;
  size?: keyof typeof SIZE;
  face?: AvatarFace;
}) {
  const seed = hash(face?.id ?? name);
  const hair = HAIR[seed % HAIR.length];
  const glasses = seed % 5 === 3;
  const expr = { brows: "M14.7 18.9h3.2M22.1 18.9h3.2", mouth: "M17.5 27q2.5 1.8 5 0", open: false };

  return (
    <span aria-hidden="true" className={`flex shrink-0 overflow-hidden rounded-full ${BG[color]} ${SIZE[size]}`}>
      <svg
        viewBox="0 0 40 40"
        className="size-full"
        fill="none"
        stroke="var(--text)"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {HAIR_BACK[hair] && <path d={HAIR_BACK[hair]} fill="var(--text)" />}
        {/* 귀 · 머리 */}
        <path d="M9.7 20.3q-2.4 1.7 0 3.8M30.3 20.3q2.4 1.7 0 3.8" />
        <ellipse cx="20" cy="22" rx="10.4" ry="11.4" fill="var(--bg-base)" />
        {HAIR_FRONT[hair] && <path d={HAIR_FRONT[hair]} fill="var(--text)" />}
        {HAIR_LINES[hair] && <path d={HAIR_LINES[hair]} />}
        {/* 눈 · 안경 · 눈썹 · 입 */}
        <circle cx="16.3" cy="22.2" r="1.15" fill="var(--text)" stroke="none" />
        <circle cx="23.7" cy="22.2" r="1.15" fill="var(--text)" stroke="none" />
        {glasses && (
          <path
            d="M13.3 22.2a3 3 0 1 0 6 0a3 3 0 1 0 -6 0M20.7 22.2a3 3 0 1 0 6 0a3 3 0 1 0 -6 0M19.3 22h1.4"
            strokeWidth="1.2"
          />
        )}
        <path d={expr.brows} strokeWidth="1.3" />
        <path d={expr.mouth} fill={expr.open ? "var(--bg-base)" : "none"} />
      </svg>
    </span>
  );
}

type Hair = "greg" | "sidePart" | "buzz" | "receding" | "long" | "bob" | "ponytail";
const HAIR: Hair[] = ["greg", "sidePart", "buzz", "long", "bob", "ponytail"];

/** 머리 뒤로 내려오는 머리카락 (얼굴보다 먼저 그린다) */
const HAIR_BACK: Partial<Record<Hair, string>> = {
  long: "M8.6 22C8 11 14 9 20 9s12 2 11.4 13l.6 11.5h-4.5l.1-9.5H12.4l.1 9.5H8z",
  bob: "M9 27C7.8 12 14 9.2 20 9.2S32.2 12 31 27h-2.6l-.4-5H12l-.4 5z",
  ponytail: "M28.6 12.6c5.6-.4 6.8 5 4.6 11.8-1-4.2-2.2-6.6-4.4-7.8z",
};

/** 얼굴 위에 덮는 머리카락 */
const HAIR_FRONT: Partial<Record<Hair, string>> = {
  sidePart:
    "M9.7 20.6C9 12 15 9.6 21 10c6 .3 10.2 3.5 9.6 10.5-2.1-3.7-6.1-5.3-10.1-4.9-3.5.3-5.7-.8-6.9-2-1 2.4-2.4 4.7-3.9 7z",
  buzz: "M10.4 18.6C11 12.5 15.5 10.5 20 10.5s9 2 9.6 8.1c-3.5-2.9-15.7-2.9-19.2 0z",
  receding:
    "M9.8 19.8c.2-3.3 1.8-5.2 3.6-5.8-.8 2-1.4 4-1.8 6.6zM30.2 19.8c-.2-3.3-1.8-5.2-3.6-5.8.8 2 1.4 4 1.8 6.6z",
  long: "M9.8 20.5C9.6 12.5 15 10 20 10s10.4 2.5 10.2 10.5c-2.4-3.5-6.2-4.7-8.7-5.9-2 2.4-7 3-11.7 5.9z",
  bob: "M10 19c.5-6.2 5-8.8 10-8.8s9.5 2.6 10 8.8z",
  ponytail: "M9.9 20C9.8 12.6 14.8 10.2 20 10.2s9.9 2.4 10.1 9.3c-3-3.6-9.6-5.2-13.6-3.4-2.4 1-4.4 2.3-6.6 3.9z",
};

/** 선으로만 그리는 머리카락 — 윔피 키드의 그 세 가닥 */
const HAIR_LINES: Partial<Record<Hair, string>> = {
  greg: "M17.6 10.9l-1.3-3.4M20.3 10.5l.2-3.8M23 10.9l1.6-3.2",
  receding: "M19.4 10.7q.6-1.8 1.8-2.4",
};

function hash(s: string) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}
