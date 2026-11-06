/*
  Cashless insurers, as a moving rail of authored wordmarks.

  WellNest is an explicitly fictional demo hospital, so these lockups are drawn here from
  scratch in one consistent system — an abstract geometric glyph in a 32-unit box plus the
  scheme's name set in the site typeface. None of them reproduces anyone's real logo artwork,
  and nothing is hot-linked.

  The rail moves continuously, pauses on hover and on keyboard focus, and under
  prefers-reduced-motion it stops and becomes an ordinary horizontally scrollable list.
*/
import type { ReactElement } from "react";
import { INSURER_MARKS, type InsurerMark } from "../../content";

const GLYPH: Record<InsurerMark["glyph"], ReactElement> = {
  shield: <path d="M16 3.5 27.5 7.8v9.4c0 6.3-5.2 10-11.5 11.3C9.7 27.2 4.5 23.5 4.5 17.2V7.8Z" />,
  bloom: <path d="M16 28.5c0-7.5-5.6-12.5-12-12.5 6.4 0 12-5 12-12.5 0 7.5 5.6 12.5 12 12.5-6.4 0-12 5-12 12.5Z" />,
  cross: (
    <>
      <circle cx="16" cy="16" r="12" />
      <path d="M16 9.5v13M9.5 16h13" />
    </>
  ),
  sunrise: (
    <>
      <path d="M5.5 22.5a10.5 10.5 0 0 1 21 0" />
      <path d="M3 27h26M16 3.5v3.5M27.2 9.8l-2.4 2.4M4.8 9.8l2.4 2.4" />
    </>
  ),
  hex: <path d="M16 3.5 27.5 10v12L16 28.5 4.5 22V10Z" />,
  diamond: (
    <>
      <path d="M16 3.5 28.5 16 16 28.5 3.5 16Z" />
      <path d="M16 11.5 20.5 16 16 20.5 11.5 16Z" />
    </>
  ),
  star: <path d="m16 3.5 3.6 9.1 9.8.5-7.6 6.2 2.5 9.5L16 23.6l-8.3 5.2 2.5-9.5-7.6-6.2 9.8-.5Z" />,
  chevron: (
    <>
      <circle cx="16" cy="16" r="12" />
      <path d="m10.5 18.5 5.5-5.5 5.5 5.5M10.5 24.5 16 19l5.5 5.5" />
    </>
  ),
  interlock: (
    <>
      <rect x="3.5" y="9" width="15" height="15" rx="4.5" />
      <rect x="13.5" y="9" width="15" height="15" rx="4.5" />
    </>
  ),
};

/** One insurer lockup: abstract glyph + name, drawn as a single SVG so every mark scales alike. */
export function InsurerLockup({ mark }: { mark: InsurerMark }) {
  const w = Math.round(44 + mark.name.length * 8.9 + 4);
  return (
    <svg className="ins-lock" viewBox={`0 0 ${w} 32`} height="30" width={w} role="img" aria-label={mark.name}>
      <g className="ins-lock-glyph" fill="none" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        {GLYPH[mark.glyph]}
      </g>
      <text className="ins-lock-word" x="44" y="21">{mark.name}</text>
    </svg>
  );
}

/**
 * The moving rail. The marks are rendered twice: the track translates by exactly -50%, so
 * the second copy is in the first copy's place when the loop restarts and the seam never shows.
 */
export function InsurerRail({ label = "Cashless, with" }: { label?: string }) {
  const run = (hidden: boolean) => (
    <ul className="ins-run" aria-hidden={hidden || undefined}>
      {INSURER_MARKS.map((m) => (
        <li key={m.name}><InsurerLockup mark={m} /></li>
      ))}
    </ul>
  );
  return (
    <section className="ins-rail" aria-label="Cashless insurance partners and government schemes">
      <div className="wrap ins-rail-in">
        <h2 className="ins-rail-label">{label}</h2>
        <div className="ins-vp" tabIndex={0} role="group" aria-label="Insurer list, scrolls continuously">
          <div className="ins-track">
            {run(false)}
            {run(true)}
          </div>
        </div>
      </div>
    </section>
  );
}
