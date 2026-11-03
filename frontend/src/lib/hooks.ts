import { useCallback, useEffect, useRef, useState } from "react";
import { api, session } from "./api";

/** Fetch JSON with loading / error state. `deps` re-run it. */
export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(!!path);
  const run = useCallback(async () => {
    if (!path) return;
    setLoading(true); setError(null);
    try { setData(await api<T>(path)); } catch (e: any) { setError(e.message); } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(() => { run(); }, [run]);
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
