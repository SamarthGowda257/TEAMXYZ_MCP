# Talkdesk chat branding — the settings only a human can change

The website now wraps the Talkdesk Chat Widget V2 in a WellNest AI frame: our header, our avatar, our launcher,
our prompt rail. **Everything inside the chat panel belongs to Talkdesk** and is set in the admin UI, not in code.
This page lists exactly what to change and where.

Code already sets the three things the SDK accepts (`frontend/src/lib/chat.ts`):

```js
window.webchat.init({
  enableEmoji: false, enableAttachments: false, enableResponsiveLayout: true,
  styles: { chatTitle: "WellNest Assistant", chatSubtitle: "Bookings, reports, insurance", chatThemeColor: "#0B5CAD" },
});
```

Nothing else about the panel can be set from the page. Do not try — the widget has no headless mode, and a
working chat matters more than a matching one.

## Change these by hand

**Where:** `pesit-hackathon.mytalkdesk.com` → **Digital Engagement** → **Touchpoints** → **WellNest_TeamXYZ**
→ the chat widget / conversation settings for that touchpoint. Publish the touchpoint after editing.

| Setting | Set it to | Why |
|---|---|---|
| Bot / assistant display name | **WellNest AI** | The site calls it WellNest AI everywhere; the panel still says "WellNest Assistant" |
| Bot avatar image | Export the mark from `frontend/src/components/WellNestAI.tsx` (`AIAvatar`) as a 128×128 PNG on a white background | So the avatar in the panel matches the one in our header and launcher |
| Primary / theme colour | `#0B5CAD` | Matches `--accent`. Already passed from code, but set it here too so it survives if the code value is ever dropped |
| Header title | **WellNest AI** | |
| Header subtitle | **Bookings, reports and insurance** | |
| Welcome message | Keep the orchestration's welcome message — do not set a second one here, or patients get two greetings | |
| Launcher / bubble | **Hide it** if the setting exists | The site ships its own branded launcher. Our CSS also hides the widget's own bubble when the panel is hosted inside our frame, but hiding it at the source is cleaner |
| Emoji and attachments | Off | Already off from code; keep the touchpoint agreeing |

## If you change the touchpoint ID or region

Both come from Render, not from code: `TALKDESK_TOUCHPOINT_ID` and `TALKDESK_REGION`. The site reads them from
`/config.js` at runtime. Change them in Render and restart; no rebuild is needed.

Check it took effect: open `https://teamxyz-mcp.onrender.com/config.js` — it prints the touchpoint, the region
and the voice number.

## How to tell the wrapper is working

1. Open the site. A round WellNest AI launcher sits bottom-right, with a one-time "Ask WellNest AI" label.
2. Click it. A 420×680 side sheet opens with **our** header (avatar, "WellNest AI", "Usually replies in seconds")
   and the Talkdesk panel filling the body.
3. Click the expand icon in that header. `/assistant` opens with the same chat in a two-column layout and the
   suggested prompts beside it.
4. Send "Book a dermatologist tomorrow". The AI answers, and the booking appears in `/admin/appointments`.
5. Send "I want to talk to a person". The ticket appears in `/admin/escalations` within about four seconds, and
   Talkdesk Conversations rings for whoever is Available.

If the panel never appears, the frame says so in plain words and offers the phone number instead of pretending
to be a chat. That fallback is deliberate.
