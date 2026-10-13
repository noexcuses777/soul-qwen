"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { getCurrentSession, SESSION_EVENT, type SoulSession } from "./soul-api";

/** One versioned persisted session across SOUL screens; completed server data only. */
export function useSoulSession() {
  const [session, setSession] = useState<SoulSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const version = useRef(0);
  const refresh = useCallback(async () => {
    const started = version.current;
    try { const current = await getCurrentSession(); if (version.current === started) { setSession(current); setError(null); } return current; }
    catch (err) { if (version.current === started) setError(err instanceof Error ? err.message : "세션을 불러오지 못했습니다."); return null; }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    let active = true;
    const started = version.current;
    const listener = (event: Event) => { version.current += 1; if (active) { setSession((event as CustomEvent<SoulSession>).detail); setError(null); } };
    window.addEventListener(SESSION_EVENT, listener);
    getCurrentSession().then(s => { if (active && version.current === started) setSession(s); }).catch(err => { if (active && version.current === started) setError(err instanceof Error ? err.message : "세션을 불러오지 못했습니다."); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; window.removeEventListener(SESSION_EVENT, listener); };
  }, []);
  return { session, setSession, loading, error, refresh };
}
