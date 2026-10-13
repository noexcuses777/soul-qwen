import type { Persona, PersonaColor } from "@/lib/types";
import { AttrRow } from "./AttrRow";
import { Chip } from "./Chip";
import { PersonaAvatar } from "./PersonaAvatar";
import { evidenceDescription, evidenceLabel } from "@/lib/evidence-presentation";

/** 선택 표시는 색 + 체크 + 버튼 글자 3중으로 한다. 색만으로 알리지 않는다. */
const BORDER: Record<PersonaColor, string> = {
  1: "border-persona-1",
  2: "border-persona-2",
  3: "border-persona-3",
  4: "border-persona-4",
  5: "border-persona-5",
};

const CHECK_BG: Record<PersonaColor, string> = {
  1: "bg-persona-1",
  2: "bg-persona-2",
  3: "bg-persona-3",
  4: "bg-persona-4",
  5: "bg-persona-5",
};

const ACCENT: Record<PersonaColor, string> = {
  1: "border-t-persona-1",
  2: "border-t-persona-2",
  3: "border-t-persona-3",
  4: "border-t-persona-4",
  5: "border-t-persona-5",
};
const TINT: Record<PersonaColor, string> = {
  1: "bg-persona-1/10",
  2: "bg-persona-2/10",
  3: "bg-persona-3/10",
  4: "bg-persona-4/10",
  5: "bg-persona-5/10",
};

/** 카드 안 라벨 폭. 시안의 62px. */
const LABEL_W = "w-[62px]";

function CheckMark() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

/**
 * 페르소나 카드. 02 추천 목록, 02-1 미리보기가 같은 모양을 쓴다.
 *
 * 이름·이용자 예시 → 상황 문장 → 판단 조건 → 확인할 점
 *
 * 의견이나 찬반 역할을 미리 정하지 않는다.
 */
export function PersonaCard({
  persona,
  selected = false,
  selectDisabled = false,
  onToggle,
  onEdit,
  /** 02-1 미리보기처럼 고르기·고치기 버튼이 필요 없는 자리 */
  readOnly = false,
}: {
  persona: Persona;
  selected?: boolean;
  selectDisabled?: boolean;
  onToggle?: () => void;
  onEdit?: () => void;
  readOnly?: boolean;
}) {
  const { name, interests, worries } = persona;
  const meta = persona.segment;

  return (
    <article
      className={`flex grow flex-col gap-3.5 rounded-card border-2 border-t-4 bg-base px-5 py-[18px] ${ACCENT[persona.color]} ${
        selected ? BORDER[persona.color] : "border-card"
      }`}
    >
      <header className="flex items-center gap-[11px]">
        <PersonaAvatar name={name} color={persona.color} size="lg" face={{ id: name }} />
        <div className="flex grow flex-col gap-px">
          <h3 className="text-[16px] font-semibold">{name}</h3>
          {meta && <p className="text-xs text-muted">{meta}</p>}
        </div>
        {selected ? (
          <span
            className={`flex size-[22px] shrink-0 items-center justify-center rounded-full text-white ${
              CHECK_BG[persona.color]
            }`}
          >
            <CheckMark />
          </span>
        ) : (
          persona.source === "custom" && (
            <span className="shrink-0 rounded-chip bg-bubble px-[9px] py-[5px] font-mono text-[10px] font-semibold tracking-[0.1em] text-ink-3">
              직접 만듦
            </span>
          )
        )}
      </header>

      {/* 이 카드의 본문. 구체적인 정황이 들어가야 대화가 뻔해지지 않는다 */}
      <p className={`rounded-chip px-3.5 py-[11px] text-sm leading-[1.75] text-ink-2 ${TINT[persona.color]}`}>{persona.situation}</p>

      <hr className="border-0 border-t border-divider" />

      {persona.notes && <AttrRow label="현재 대안" labelWidth={LABEL_W} align="start">{persona.notes}</AttrRow>}
      {!!persona.criticalUnknowns?.length && <AttrRow label="확인할 점" labelWidth={LABEL_W} align="start"><span className="flex flex-wrap gap-[5px]">{persona.criticalUnknowns.map((item, index) => <Chip key={index} tone="conflict">{item}</Chip>)}</span></AttrRow>}
      {persona.evidenceLevel !== undefined && <AttrRow label="근거" labelWidth={LABEL_W} align="start"><span title={evidenceDescription(persona.evidenceLevel)}><Chip tone="action">{evidenceLabel(persona.evidenceLevel)}</Chip></span></AttrRow>}
      {(interests.length > 0 || worries.length > 0) && <div className="flex flex-col gap-[9px]">
        <AttrRow label="관심사" labelWidth={LABEL_W} align="start">
          <span className="flex flex-wrap gap-[5px]">
            {interests.map((item) => (
              <Chip key={item}>{item}</Chip>
            ))}
          </span>
        </AttrRow>
        {/* Generated conditions may be unknown; do not require a negative opinion. */}
        <AttrRow label="걱정" labelWidth={LABEL_W} align="start">
          <span className="flex flex-wrap gap-[5px]">
            {worries.map((item) => (
              <Chip key={item} tone="conflict">
                {item}
              </Chip>
            ))}
          </span>
        </AttrRow>
      </div>

      }

      {persona.quote && (
        <blockquote className="rounded-chip bg-panel px-3.5 py-[11px] text-sm leading-relaxed text-ink-2">
          &ldquo;{persona.quote}&rdquo;
        </blockquote>
      )}

      {(persona.checkpoint || persona.reason) && (
        <div className="flex flex-col gap-[7px]">
          {persona.checkpoint && !persona.criticalUnknowns?.length && (
            <AttrRow label="물어볼 것" labelWidth={LABEL_W}>
              {persona.checkpoint}
            </AttrRow>
          )}
          {persona.reason && (
            <AttrRow label="고른 이유" labelWidth={LABEL_W}>
              <span className={`font-medium ${selected ? "text-brand" : "text-ink-3"}`}>
                {persona.reason}
              </span>
            </AttrRow>
          )}
        </div>
      )}

      {!readOnly && (
        <div className="mt-auto flex gap-2 pt-1">
          <button
            type="button"
            onClick={onEdit}
            className="h-11 grow rounded-btn border border-btn-border bg-base text-sm text-ink-2"
          >
            고치기
          </button>
          <button
            type="button"
            onClick={onToggle}
            disabled={!selected && selectDisabled}
            aria-pressed={selected}
            className={
              selected
                ? "h-11 grow rounded-btn bg-brand text-sm font-semibold text-white"
                : "h-11 grow rounded-btn border border-btn-border bg-base text-sm text-ink-2 disabled:text-muted"
            }
          >
            {selected ? "선택됨" : "고르기"}
          </button>
        </div>
      )}
    </article>
  );
}
