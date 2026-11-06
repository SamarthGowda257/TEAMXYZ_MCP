import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { Boundary } from "./components/Boundary";
// Self-hosted: the CSP allows styles and fonts from 'self' only, so a fonts.googleapis.com
// link would silently fail. Petrona carries the display voice, Lexend every UI and body text.
import "@fontsource-variable/petrona";
import "@fontsource-variable/lexend";
import "@fontsource/atkinson-hyperlegible/400.css";
import "@fontsource/atkinson-hyperlegible/700.css";
import "./styles/tokens.css";
import "./styles/tw.css";       // Tailwind utilities (preflight off) for the component libraries
import "./styles/legacy.css";   // portal / booking / auth rules, re-themed by the token aliases
import "./styles/site.css";
import "./styles/pages.css";
import "./styles/public.css";   // /doctors /insurance /contact /about /specialities /visitors
import "./styles/app.css";
import "./styles/ai.css";
import "./styles/record.css";
import "./styles/shop.css";
import "./styles/admin.css";

try {
  if (localStorage.getItem("wellnest_size") === "lg") document.documentElement.dataset.size = "lg";
} catch { /* private mode */ }

// Smooth, inertial page scrolling, with ScrollTrigger reading its position rather than the window's.
if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  import("lenis").then(async ({ default: Lenis }) => {
    const lenis = new Lenis({ duration: 1.05, smoothWheel: true });
    (window as any).__lenis = lenis;
    const raf = (t: number) => { lenis.raf(t); requestAnimationFrame(raf); };
    requestAnimationFrame(raf);
    const { bindLenis } = await import("./lib/motion");
    bindLenis(lenis);
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Boundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </Boundary>
  </React.StrictMode>,
);
