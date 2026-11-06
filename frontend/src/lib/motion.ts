/*
  One orchestrated motion grammar for the Persuade surfaces, built on GSAP ScrollTrigger.

  Three authored moments, not scattered effects:
    data-reveal          a section's children rise once, staggered, as it enters
    data-parallax="n"    a decorative layer drifts against the scroll (never text, never controls)
    data-curtain         the dark band's inner panel unmasks as it crosses the viewport

  Content is visible by default in markup; `.js [data-reveal]` hides it only once JS is running,
  so a crawler or a failed bundle still shows a complete page. prefers-reduced-motion skips
  everything and renders the final state immediately.
*/
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

let registered = false;

export function initMotion(): () => void {
  if (typeof window === "undefined") return () => {};

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) {
    document.querySelectorAll<HTMLElement>("[data-reveal]").forEach((el) => { el.style.opacity = "1"; });
    return () => {};
  }

  if (!registered) { gsap.registerPlugin(ScrollTrigger); registered = true; }
  document.documentElement.classList.add("js");

  const ctx = gsap.context(() => {
    // 1. Section reveals. Stagger is capped at 8 children: past that the tail reads as lag.
    gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((el) => {
      const targets = el.hasAttribute("data-reveal-self")
        ? [el]
        : Array.from(el.children).slice(0, 8) as HTMLElement[];
      if (!targets.length) return;
      gsap.set(el, { opacity: 1 });
      gsap.set(targets, { opacity: 0, y: 26 });
      gsap.to(targets, {
        opacity: 1,
        y: 0,
        duration: 0.62,
        stagger: 0.075,
        ease: "power2.out",
        scrollTrigger: { trigger: el, start: "top 86%", once: true },
      });
    });

    // 2. Parallax on decorative layers only. Small delta so foreground never desyncs.
    gsap.utils.toArray<HTMLElement>("[data-parallax]").forEach((layer) => {
      const depth = Number(layer.dataset.parallax || "1");
      gsap.to(layer, {
        yPercent: -6 * depth,
        ease: "none",
        scrollTrigger: {
          trigger: layer.parentElement || layer,
          scrub: 0.6,
          onToggle: (self) => { layer.style.willChange = self.isActive ? "transform" : "auto"; },
        },
      });
    });

    // 3. The one signature moment: the dark band unmasks from the bottom as it enters.
    gsap.utils.toArray<HTMLElement>("[data-curtain]").forEach((el) => {
      gsap.fromTo(
        el,
        { clipPath: "inset(14% 0% 0% 0% round 20px)", opacity: 0.55 },
        {
          clipPath: "inset(0% 0% 0% 0% round 20px)",
          opacity: 1,
          ease: "none",
          scrollTrigger: { trigger: el, start: "top 92%", end: "top 48%", scrub: 0.5 },
        },
      );
    });
  });

  // Fonts and images change layout; recompute once they land.
  const refresh = () => ScrollTrigger.refresh();
  if (document.fonts?.ready) document.fonts.ready.then(refresh).catch(() => {});
  window.addEventListener("load", refresh, { once: true });

  /*
   * Safety net. A reveal that never fires leaves real content invisible forever — a far worse
   * failure than an un-animated page. If anything is still transparent while sitting inside the
   * viewport, show it. Runs twice, then stops.
   */
  const rescue = () => {
    document.querySelectorAll<HTMLElement>("[data-reveal] > *, [data-reveal][data-reveal-self]").forEach((el) => {
      if (getComputedStyle(el).opacity !== "0") return;
      const r = el.getBoundingClientRect();
      if (r.top < window.innerHeight && r.bottom > 0) gsap.set(el, { opacity: 1, y: 0 });
    });
  };
  const t1 = window.setTimeout(rescue, 1200);
  const t2 = window.setTimeout(rescue, 4000);

  return () => {
    ctx.revert();
    window.clearTimeout(t1);
    window.clearTimeout(t2);
    window.removeEventListener("load", refresh);
  };
}

/** Lenis drives the scroll position, so ScrollTrigger has to read from it rather than the window. */
export function bindLenis(lenis: { on: (event: "scroll", cb: () => void) => unknown }): void {
  if (!registered) return;
  lenis.on("scroll", () => ScrollTrigger.update());
}
