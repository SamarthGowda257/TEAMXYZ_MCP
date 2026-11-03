import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "@fontsource/dm-serif-display/400.css";
import "@fontsource-variable/manrope";
import "./styles/tokens.css";
import "./styles/site.css";
import "./styles/pages.css";
import "./styles/app.css";

try { if (localStorage.getItem("careline_size") === "lg") document.documentElement.dataset.size = "lg"; } catch { /* private mode */ }

// Smooth, inertial page scrolling (skipped for people who prefer reduced motion).
if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  import("lenis").then(({ default: Lenis }) => {
    const lenis = new Lenis({ duration: 1.1, smoothWheel: true });
    (window as any).__lenis = lenis;
    const raf = (t: number) => { lenis.raf(t); requestAnimationFrame(raf); };
    requestAnimationFrame(raf);
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
