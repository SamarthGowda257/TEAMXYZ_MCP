import { useCallback, useEffect, useRef, useState } from "react";
import { api, session } from "./api";

const LIVE_MS = 8000;

/** Fetch JSON with loading / error state. `deps` re-run it.
 *  `live` keeps it current while the tab is visible: a booking made in the Talkdesk chat or by phone never reaches the
 *  page any other way, because the widget talks to Talkdesk directly. Live refreshes show no spinner, keep the last data
 *  on a failed request, and only re-render when the answer changed, so open forms are not disturbed. */
export function useApi<T>(path: string | null, deps: unknown[] = [], opts: { live?: boolean } = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(!!path);
  const last = useRef("");
  const run = useCallback(async () => {
    if (!path) return;
    setLoading(true); setError(null);
    try { const d = await api<T>(path); last.current = JSON.stringify(d); setData(d); }
    catch (e: any) { setError(e.message); } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(() => { run(); }, [run]);
  const live = !!opts.live && !!path;
  useEffect(() => {
    if (!live) return;
    const refresh = async () => {
      if (document.hidden) return;
      try {
        const d = await api<T>(path!);
        const s = JSON.stringify(d);
        if (s !== last.current) { last.current = s; setData(d); }
      } catch { /* keep what is on screen; the next tick tries again */ }
    };
    const timer = window.setInterval(refresh, LIVE_MS);
    window.addEventListener("focus", refresh);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", refresh); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live, path, ...deps]);
  return { data, error, loading, reload: run, setData };
}

export function useLoggedIn() {
  const [li, setLi] = useState(session.loggedIn());
  useEffect(() => {
    const f = () => setLi(session.loggedIn());
    window.addEventListener("wellnest-auth", f);
    return () => window.removeEventListener("wellnest-auth", f);
  }, []);
  return li;
}

/** Section entrances: children with .rise get .in when they scroll into view (once). */
export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !("IntersectionObserver" in window)) return;
    document.documentElement.classList.add("js");
    const items = el.querySelectorAll<HTMLElement>(".rise");
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    items.forEach((i) => io.observe(i));
    const safety = window.setTimeout(() => items.forEach((i) => i.classList.add("in")), 2500);
    return () => { io.disconnect(); window.clearTimeout(safety); };
  });
  return ref;
}

export function useTextSize(): [boolean, (v: boolean) => void] {
  const [lg, setLg] = useState(document.documentElement.dataset.size === "lg");
  const set = (v: boolean) => {
    if (v) document.documentElement.dataset.size = "lg"; else delete document.documentElement.dataset.size;
    try { if (v) localStorage.setItem("wellnest_size", "lg"); else localStorage.removeItem("wellnest_size"); } catch { /* ignore */ }
    setLg(v);
    window.dispatchEvent(new Event("wellnest-size"));
  };
  useEffect(() => {
    const f = () => setLg(document.documentElement.dataset.size === "lg");
    window.addEventListener("wellnest-size", f);
    return () => window.removeEventListener("wellnest-size", f);
  }, []);
  return [lg, set];
}
