# DESIGN.md — WellNest Hospitals

Durable visual decisions for the WellNest web surfaces. Product truth lives in `PRODUCT.md`.
Written 4 Nov 2026 for the `frontend-v3` redesign.

## Overview

**The world is pinned, not invented.** The repo owner asked for a clinical **hospital** look and explicitly
ruled out a dark theme. That is a brief, and the brief wins: this document records and sharpens the identity
already in `frontend/src/styles/tokens.css` rather than replacing it with a new visual world. The deep-teal
and dark-mode direction in `docs/FRONTEND_REDESIGN_PROMPT.md` §2 is superseded by §12 of that file.

The reference point is the **printed hospital wayfinding system** — the signage, floor directories, ward
boards and appointment cards a patient actually reads inside an Indian multi-specialty hospital. That world
is white, high-contrast, heavily ruled, numbered, and completely unambiguous, because people read it when
they are anxious or in pain. It gives us: generous white ground, one confident blue, hairline rules instead
of drop shadows, tabular numerals, and plain labels over clever ones.

What it is explicitly not: a SaaS landing page, a wellness-startup gradient, or a glassmorphic dashboard.

### Modes per surface

| Surface | Mode | What success looks like |
|---|---|---|
| `/`, `/departments`, `/doctors`, `/about`, `/policies`, `/contact` | **Persuade** | A visitor believes this is a real, competent hospital and starts a booking or a chat |
| `/assistant`, chat modal | **Operate** | The patient gets an answer; the interface recedes around the Talkdesk panel |
| `/portal/*` | **Operate** | A patient finds their appointment and changes it without hesitation |
| `/admin/*` | **Operate** | Staff scan a queue under time pressure; density and precision beat expression |

## Colors

Light mode only. No `prefers-color-scheme` branch, no `data-theme`. A dark variant is out of scope by decision.

### Brand & accent
| Token | Value | Use |
|---|---|---|
| `--accent` | `#0b5cad` | Medical blue. Primary actions, links, active nav, focus accents |
| `--accent-deep` | `#08458a` | Hover and pressed states |
| `--sky` | `#e8f2fd` | Tint fill behind quiet buttons, selected rows, info callouts |
| `--teal` | `#0e8a7d` | Reserved for "ready / healthy / complete" states only |

### Surface
| Token | Value | Use |
|---|---|---|
| `--bg` | `#ffffff` | Page ground. The default is white and stays white |
| `--surface` | `#f3f7fc` | Alternating bands, admin shell background |
| `--surface-2` | `#e7f0fa` | Table headers, inset panels |
| `--card` | `#ffffff` | Cards sit on tinted bands, not on white-on-white |
| `--border` / `--line` | `#dde6f0` / `#e6edf5` | Hairline rules. This system rules, it does not shadow |

### Text
`--ink #0d2240` for body and headings · `--muted #4a5b72` for secondary · `--faint #5c6c82` for metadata.
Never put `--faint` on `--surface-2` at small sizes; it fails AA.

### Semantic
`--alert #d0312d` + `--alert-tint #fdecea` — **emergency and destructive only.** Red is a promise in a
hospital; it may not be spent on a validation hint or a chart series.
`--ok #1f7a4d` / `--ok-tint #e3f4ea` · `--marigold #f2a900` (focus ring) · `--warn-tint` / `--warn-ink`.

Priority chips in the admin Escalations queue: urgent uses `--alert`, normal uses `--accent`. No third colour.

## Typography

**DM Serif Display** for display headings (`.serif`, h1/h2 on Persuade surfaces) — the one warm, human note
against an otherwise systematic page. **Manrope Variable** for all UI, headings on Operate surfaces, and body.
**Atkinson Hyperlegible** is available for the large-text accessibility mode.

All three are self-hosted via `@fontsource`. **Google Fonts is blocked by the CSP — never add a `<link>` to
fonts.googleapis.com.**

Scale: `--step-small .9375rem` · `--step-body 1.0625rem` · `--step-lead` · `--step-head` · `--step-hero`,
the last three fluid via `clamp()`. Body line-height 1.65, headings 1.2, `letter-spacing: -0.02em` on headings.
`font-variant-numeric: tabular-nums` is global — times, fees, booking IDs and table columns must align.

Booking IDs, report codes and handoff codes render in a `.code` style: tabular, `letter-spacing: .04em`,
slightly darker. On voice they are read character by character; on screen they are never broken across lines.

## Layout

- Container `--max 1520px`, gutter `--margin: clamp(16px, 4.5vw, 88px)`, collapsing to 16px under 860px.
- Spacing steps: 4, 8, 12, 16, 24, 32, 48, 64, 96. Nothing between.
- Admin shell: fixed 248px sidebar, 60px top bar, fluid content, single column under 1024px with the
  sidebar collapsing to a slide-over.
- Radius `--radius 14px` for cards and inputs, `999px` for buttons and chips. No other radii.
- Depth: hairline borders first, `--shadow` only for genuinely floating things — the chat modal, a drawer, a
  sticky header once scrolled. Cards on tinted bands use a border, not a shadow.

## Components

**Buttons** (`.btn`): 48px min height (40px for `.btn-sm`), pill radius, `--font-display` 700.
`.btn-primary` solid blue · `.btn-quiet` white with `--control` border · `.btn-danger` / `.btn-emergency` red.
1px translate on `:active`. Disabled drops to 50% and keeps the cursor honest.

**Fields** (`.field` / `.input`): 50px min height, label above in 700, optional `.hint` below in `--muted`,
`.error-text` in `--alert`. Focus is a blue border plus a 3px `color-mix` halo.

**Focus (global):** `3px solid var(--marigold)` at `3px` offset. Marigold on a blue-and-white page is the one
colour nothing else uses, which is exactly why it is the focus ring. Never remove it.

**Cards:** white on a tinted band, 1px `--border`, 14px radius, 24px padding.

**Chips:** pill, 12px/700, tinted background with its own ink colour. Status vocabulary is fixed —
booked, confirmed, rescheduled, cancelled, completed; open, in progress, resolved.

**Tables (admin):** `--surface-2` header, hairline row rules, tabular numerals, 44px rows, whole row is the
click target when a detail drawer exists. Every table has a loading skeleton and a written empty state.

**Emergency banner:** persistent, `--alert-tint` ground with `--alert` ink, "Medical emergency? Call 108" with
108 as a `tel:` link. Appears on every public and patient page, above the header. It is never dismissible.

## WellNest AI identity

An original SVG mark: a rounded nest arc cradling a soft pulse line, drawn in `--accent` on `--sky`. No face,
no robot, no sparkles — the pulse line is the only motif, and it is the same line that appears in the loading
indicator. Sizes 24 / 32 / 48. An "online" dot in `--teal` sits bottom-right of the avatar at 32px and above.

The launcher is a 60px circular button, bottom-right, 24px from each edge, `--shadow`, avatar centred, with a
one-line label on first load ("Ask WellNest AI") that collapses after the first interaction.

**The Talkdesk panel is not ours to restyle.** We own the frame around it — header, avatar, name, "Usually
replies in seconds", the suggested-prompt rail and the close control. Inside the panel, only `chatTitle`,
`chatSubtitle` and `chatThemeColor` are ours; everything else is a Talkdesk touchpoint setting, documented in
`docs/TALKDESK_CHAT_BRANDING.md`. Never fake a message bubble we did not receive.

## Motion

Lenis smooth scroll stays. `.rise` reveals (28px, 900ms, `--ease-out`) on Persuade surfaces only — **never** in
the admin console or the portal, where content must be present the moment it loads. Transitions are 150–200ms
on colour and border. `prefers-reduced-motion: reduce` disables all of it, already wired globally.

## Do's and Don'ts

**Do**
- Keep the page white and let the blue do one job at a time.
- Use hairline rules and tinted bands for structure.
- Write the empty state and the error state before the happy path.
- Pull every doctor, fee, hour and slot from the API.
- Say "simulated" where a channel is simulated.

**Don't**
- Add a dark theme, a gradient hero, a glass panel or a neon accent.
- Spend red on anything but emergency and destructive actions.
- Load a font, script or stylesheet from any CDN — the CSP blocks it and the page will silently break.
- Invent a doctor, a fee, a visiting hour or a policy that the API and knowledge base do not have.
- Render a chat transcript the backend cannot actually produce.

## Responsive

Breakpoints 640 / 860 / 1024 / 1280. Must be correct at 360px with no horizontal scroll. Touch targets 44px
minimum. The chat modal is a 420×680 side sheet on desktop and full-screen on mobile. Admin tables become
stacked cards under 860px rather than scrolling sideways.

## Known gaps

- No dark theme, by decision.
- Admin charts are light-weight inline SVG; no charting library is added.
- Conversation detail is a reconstructed activity timeline, because `interaction_notes` stores summaries and
  outcomes, not turn-by-turn messages. Verbatim transcripts exist only inside Talkdesk.
