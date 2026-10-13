"use client";

import { useState } from "react";

/**
 * 지울 수 있는 키워드 칩 + 추가 입력. 02-1 의 관심사·걱정에서 쓴다.
 * 색만으로 의미를 전하지 않도록 라벨은 바깥에서 붙인다.
 */
export function EditableChips({
  items,
  onChange,
  tone = "neutral",
  addLabel = "추가",
  inputLabel,
}: {
  items: string[];
  onChange: (next: string[]) => void;
  tone?: "neutral" | "conflict";
  addLabel?: string;
  /** 추가 입력칸의 접근성 이름 */
  inputLabel: string;
}) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");

  const chip =
    tone === "conflict"
      ? "bg-conflict-bg text-conflict-fg"
      : "bg-bubble text-ink-2";

  const commit = () => {
    const value = draft.trim();
    if (value && !items.includes(value)) onChange([...items, value]);
    setDraft("");
    setAdding(false);
  };

  return (
    <div className="flex flex-wrap items-center gap-[7px]">
      {items.map((item) => (
        <span
          key={item}
          className={`flex items-center gap-[7px] rounded-chip px-[11px] py-[7px] text-[13px] ${chip}`}
        >
          {item}
          <button
            type="button"
            onClick={() => onChange(items.filter((x) => x !== item))}
            aria-label={`${item} 지우기`}
            className="flex size-5 items-center justify-center"
          >
            <svg
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </span>
      ))}

      {adding ? (
        <input
          autoFocus
          type="text"
          value={draft}
          aria-label={inputLabel}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commit();
            }
            if (e.key === "Escape") {
              setDraft("");
              setAdding(false);
            }
          }}
          className="h-[33px] w-40 rounded-chip border border-input-border bg-input px-[11px] text-[13px]"
        />
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="flex items-center gap-1.5 rounded-chip border border-dashed border-btn-border bg-base px-[11px] py-[7px] text-[13px] text-ink-3"
        >
          <svg
            width="11"
            height="11"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            aria-hidden="true"
          >
            <path d="M12 5v14M5 12h14" />
          </svg>
          {addLabel}
        </button>
      )}
    </div>
  );
}
