import { PersonaAvatar } from "@/components/PersonaAvatar";
import type { PersonaColor } from "@/lib/types";
import { normalize } from "@/lib/korean-text";
import { chatInteractionLabel } from "@/lib/chat-presentation";

/**
 * 단체 대화(04)와 발화 대기(07-1)가 함께 쓰는 조각.
 * 페르소나는 색 + 이니셜 + 이름 3중으로 표시한다 (CLAUDE.md 7절).
 */

const NAME_COLOR: Record<PersonaColor, string> = {
  1: "text-persona-1",
  2: "text-persona-2",
  3: "text-persona-3",
  4: "text-persona-4",
  5: "text-persona-5",
};

const DOT_COLOR: Record<PersonaColor, string> = {
  1: "bg-persona-1",
  2: "bg-persona-2",
  3: "bg-persona-3",
  4: "bg-persona-4",
  5: "bg-persona-5",
};

/** ROUND 구분선: 라운드 구조(첫 반응 → 상호 토론 → 자유 질문)를 대화 중에 보여준다. */
export function RoundDivider({ round, label }: { round: number; label: string }) {
  return (
    <div className="flex items-center gap-3" role="separator" aria-label={`라운드 ${round}, ${label}`}>
      <div className="h-px grow bg-line" />
      <p className="font-mono text-[11px] font-medium tracking-[0.12em] text-muted">
        ROUND {String(round).padStart(2, "0")} · {label}
      </p>
      <div className="h-px grow bg-line" />
    </div>
  );
}

/** 페르소나 한 명의 발언 말풍선 */
export function PersonaMessage({
  name,
  segment,
  color,
  children,
}: {
  name: string;
  segment?: string;
  color: PersonaColor;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-[11px]">
      <PersonaAvatar name={name} color={color} />
      <div className="flex max-w-[620px] flex-col gap-[5px]">
        <p className={`text-xs font-semibold ${NAME_COLOR[color]}`}>{name}{segment && <span className="ml-2 font-normal text-muted">{segment}</span>}</p>
        <div className="whitespace-pre-wrap rounded-[4px_14px_14px_14px] border border-card bg-base px-4 py-[13px] text-[15px] leading-[1.72] text-ink-2">
          {typeof children === "string" ? normalize(children) : children}
        </div>
      </div>
    </div>
  );
}

/** 지금 말하는 중인 페르소나. 점 세 개가 그 사람 색으로 깜빡인다. */
export function TypingMessage({ name, color }: { name: string; color: PersonaColor }) {
  return (
    <div className="flex gap-[11px]" role="status">
      <PersonaAvatar name={name} color={color} />
      <div className="flex flex-col gap-[5px]">
        <p className={`text-xs font-semibold ${NAME_COLOR[color]}`}>{name}</p>
        <div className="flex items-center gap-1.5 rounded-[4px_14px_14px_14px] border border-card bg-base px-[18px] py-4">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              aria-hidden="true"
              className={`size-[7px] rounded-full ${DOT_COLOR[color]} motion-safe:animate-pulse`}
              style={{ animationDelay: `${i * 0.2}s`, opacity: 1 - i * 0.3 }}
            />
          ))}
          <span className="sr-only">{name}님이 답하는 중</span>
        </div>
      </div>
    </div>
  );
}

/** 다음에 말할 사람 + 여기서 멈추기. 세 명이 순차로 말해 대기가 길어서, 기다리는 동안에도 할 수 있는 일을 남긴다. */
export function NextSpeaker({
  name,
  color,
  onStop,
}: {
  name: string;
  color: PersonaColor;
  onStop?: () => void;
}) {
  return (
    <div className="flex items-center gap-2.5 pt-0.5">
      <div className="flex h-9 items-center gap-[9px] rounded-full bg-bubble px-3.5">
        <span className="font-mono text-[10px] font-semibold tracking-[0.12em] text-muted">다음</span>
        <span className="flex items-center gap-1.5">
          <PersonaAvatar name={name} color={color} size="sm" />
          <span className="text-[13px] text-ink-2">{name}</span>
        </span>
      </div>
      <button
        type="button"
        onClick={onStop}
        className="h-11 rounded-full border border-btn-border bg-base px-3.5 text-[13px] text-ink-3"
      >
        여기서 멈추기
      </button>
    </div>
  );
}

/**
 * 하단 입력창. 페르소나가 말하는 동안에도 질문은 적어둘 수 있게 입력은 열어두고 보내기만 막는다.
 */
export function ChatComposer({
  value,
  onChange,
  onSend,
  sending = false,
  inputId = "say",
  maxLength = 500,
  placeholder = "세 명에게 묻고 싶은 것을 적어주세요",
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  /** 페르소나가 말하는 중이면 보내기를 막는다 */
  sending?: boolean;
  inputId?: string;
  maxLength?: number;
  placeholder?: string;
}) {
  const disabled = sending || !value.trim();
  return (
    <form
      className="flex w-full items-center gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (!disabled) onSend();
      }}
    >
      <label htmlFor={inputId} className="sr-only">
        하고 싶은 말
      </label>
      <input
        id={inputId}
        type="text"
        value={value}
        maxLength={maxLength}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-[50px] grow rounded-[14px] border border-input-border bg-base px-[18px] text-[15px] text-ink placeholder:text-muted"
      />
      <button
        type="submit"
        aria-label={sending ? "답하는 중이라 아직 보낼 수 없어요" : "보내기"}
        disabled={disabled}
        className="flex size-[50px] shrink-0 items-center justify-center rounded-[14px] bg-brand disabled:cursor-not-allowed disabled:bg-btn-border"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--bg-base)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M12 19V5M5 12l7-7 7 7" />
        </svg>
      </button>
    </form>
  );
}

/** 사용자 말풍선 (오른쪽, 브랜드색). compact 는 1:1 패널용 작은 크기 */
export function UserMessage({ children, compact = false }: { children: React.ReactNode; compact?: boolean }) {
  return (
    <div className={`flex flex-col gap-[5px] self-end ${compact ? "max-w-[330px]" : "max-w-[580px]"}`}>
      <p className={`self-end font-semibold text-muted ${compact ? "text-[11px]" : "text-xs"}`}>나</p>
      <div
        className={`whitespace-pre-wrap bg-brand text-white ${
          compact
            ? "rounded-[12px_4px_12px_12px] px-3.5 py-[11px] text-sm leading-[1.7]"
            : "rounded-[14px_4px_14px_14px] px-4 py-[13px] text-[15px] leading-[1.72]"
        }`}
      >
        {children}
      </div>
    </div>
  );
}

/**
 * 단체 대화 머리: 겹친 아바타 · 제목 · 이름과 라운드 · "따로" 버튼(1:1 열기).
 * 1:1 은 상단 참가자 칩을 눌러 오른쪽 패널로 연다 (DECISIONS.md 04 B안).
 */
export function ChatRoomHeader({
  personas,
  round,
  interaction = "auto",
  onOpenDm,
}: {
  personas: { id: string; name: string; color: PersonaColor }[];
  round: number;
  interaction?: "auto" | "direct" | "interactive";
  onOpenDm: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-3.5 pb-1">
      <div className="flex shrink-0" aria-hidden="true">
        {personas.map((p, i) => (
          <span key={p.id} className={`rounded-full border-2 border-alt ${i > 0 ? "-ml-[9px]" : ""}`}>
            <PersonaAvatar name={p.name} color={p.color} />
          </span>
        ))}
      </div>
      <div className="flex grow flex-col gap-0.5">
        <h1 className="text-[16px] font-semibold">
          {personas.length === 3 ? "세 명과" : `${personas.length}명과`} 함께 이야기하는 중
        </h1>
        <p className="font-mono text-[11px] tracking-[0.1em] text-muted">
          {personas.map((p) => p.name).join(" · ")} — {round ? `질문 ${round}개` : "대화 준비"} · {chatInteractionLabel(interaction)}
        </p>
      </div>
      <div className="flex items-center gap-[7px]">
        <span className="mr-0.5 font-mono text-[10px] font-semibold tracking-[0.12em] text-muted">한 명에게 묻기</span>
        {personas.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => onOpenDm(p.id)}
            aria-label={`${p.name}님에게 지정 질문`}
            className="flex size-11 items-center justify-center rounded-full"
          >
            <span className="rounded-full border-2 border-base">
              <PersonaAvatar name={p.name} color={p.color} />
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

/** 입력창 위 "물어볼 질문" 칩. 과거 행동을 묻는 질문만 넣는다. */
export function QuestionChips({
  questions,
  onPick,
  onMore,
}: {
  questions: string[];
  onPick: (q: string) => void;
  onMore: () => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="shrink-0 font-mono text-[11px] font-medium tracking-[0.12em] text-muted">물어볼 질문</span>
      {questions.map((q) => (
        <button
          key={q}
          type="button"
          onClick={() => onPick(q)}
          className="h-11 truncate rounded-chip border border-input-border bg-base px-[13px] text-[13px] text-ink-2"
        >
          {q}
        </button>
      ))}
      <button
        type="button"
        onClick={onMore}
        aria-label="다른 질문 보기"
        className="flex size-11 shrink-0 items-center justify-center rounded-chip border border-input-border bg-base"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--text-muted)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M21 12a9 9 0 1 1-3-6.7" />
          <path d="M21 4v5h-5" />
        </svg>
      </button>
    </div>
  );
}
