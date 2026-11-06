import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { Chip, Empty, Filters, Loading, Panel, Status, useOps } from "../adminKit";

/**
 * Today — what the retired /dashboard showed, now the front page of the control panel.
 * Everything polls, because the AI is writing to this database while staff read it.
 */

type Summary = {
  date: string; now: string; email_mode?: string; db?: string;
  summary: Record<string, number>;
  schedule: { department: string; booked: number; capacity: number }[];
};
type Feed = {
  activity: { day: string; at: string; action: string; patient: string; summary: string; ref: string; channel: string; ok?: boolean }[];
  offers: { code: string; patient: string; doctor: string; slot: string; status: string; seconds_left: number }[];
  handoffs: { code: string; summary: string; at: string; phone: string; priority: string; status: string }[];
  outbox: { template: string; channel: string; to: string; at: string; status: string }[];
  nurse_alerts: { reason: string }[];
};
type Metrics = { tools: { tool: string; count: number }[]; p50_ms: number; p95_ms: number; total_calls: number };

const ACTION: Record<string, string> = {
  book_appointment: "Booked", cancel_appointment: "Cancelled", reschedule_appointment: "Moved",
  accept_waitlist_offer: "Waitlist booked", waitlist_offer: "Slot offered", join_waitlist: "Joined waitlist",
  create_handoff: "Escalated", email_lab_report: "Report emailed", request_assistance: "Help arranged",
  register_patient: "Registered", web_signup: "Signed up", request_callback: "Call back",
  set_patient_preferences: "Preferences", send_payment_link: "Payment link",
  send_caregiver_update: "Caregiver told", request_prescription_refill: "Refill asked",
  flag_nurse_alert: "Nurse alert", record_checkin: "Check-in", outbound_call: "Outbound call",
  staff_doctor_added: "Doctor added", staff_doctor_updated: "Doctor edited", staff_doctor_removed: "Doctor removed",
  staff_department_added: "Department added", staff_department_updated: "Department edited",
  staff_department_removed: "Department removed", staff_medicine_added: "Medicine added",
  staff_medicine_updated: "Stock changed", staff_medicine_removed: "Medicine removed",
  staff_order_status: "Order moved", staff_wallet_adjust: "Wallet adjusted",
  staff_appointment_status: "Visit marked", staff_patient_updated: "Record edited",
  staff_insurer_updated: "Insurer edited",
};

export function Today() {
  const sum = useOps<Summary>("/api/ops/summary", 15000);
  const feed = useOps<Feed>("/api/ops/feed", 15000);
  const met = useOps<Metrics>("/api/metrics", 20000);
  const [channel, setChannel] = useState("");

  const k = sum.data?.summary || {};
  const m = met.data;

  const kpis = [
    { label: "Bookings today", value: k.bookings_today, note: `${k.upcoming_bookings ?? 0} upcoming in all` },
    { label: "Cancellations today", value: k.cancellations_today, note: "freed slots go to the waitlist" },
    { label: "Refilled from waitlist", value: k.refilled_from_waitlist, note: "cancelled slots saved", good: true },
    { label: "Offers open", value: k.open_offers, note: "waiting for a patient's answer" },
    {
      label: "Escalations open", value: k.open_handoffs,
      note: k.urgent_handoffs_today ? `${k.urgent_handoffs_today} urgent today` : "none urgent",
      bad: !!k.open_handoffs,
    },
    {
      label: "Tool time p95", value: m?.total_calls ? `${Math.round(m.p95_ms)} ms` : "—",
      note: m?.total_calls ? `${m.total_calls} tool calls since restart` : "no tool calls since restart",
    },
  ];

  const sched = (sum.data?.schedule || []).filter((d) => d.capacity);
  const activity = (feed.data?.activity || []).filter((a) => !channel || a.channel === channel);

  return (
    <>
      <ul className="ad-kpis">
        {kpis.map((x) => (
          <li key={x.label} className={x.bad ? "ad-kpi ad-kpi-alert" : "ad-kpi"}>
            <span className="ad-kpi-label">{x.label}</span>
            <strong className="ad-kpi-value">{sum.loading && x.value == null ? "…" : x.value ?? "—"}</strong>
            <span className="ad-kpi-sub">{x.note}</span>
          </li>
        ))}
      </ul>

      <div className="ad-two">
        <Panel title="OPD fill today" action={<span className="ad-panel-note">booked of available slots</span>}>
          {sum.loading && !sum.data ? <Loading rows={6} /> : !sched.length ? (
            <Empty title="No clinics running today" hint="Department fill appears once doctors have slots on this date." />
          ) : (
            <ul className="ad-bars">
              {sched.map((d) => {
                const pct = Math.round((d.booked / d.capacity) * 100);
                return (
                  <li key={d.department}>
                    <span className="ad-bar-name">{d.department}</span>
                    <span className="ad-bar-track" role="img" aria-label={`${pct}% full`}>
                      <i className={pct >= 85 ? "is-full" : ""} style={{ width: `${Math.max(Math.min(pct, 100), 2)}%` }} />
                    </span>
                    <span className="ad-bar-num ad-num">{d.booked}/{d.capacity}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel
          title="Live activity"
          action={
            <div className="ad-head-tools">
              <Filters label="Channel" value={channel} onChange={setChannel}
                       options={[["", "All"], ["chat", "Chat"], ["voice", "Voice"], ["web", "Web"], ["staff", "Staff"]]} />
              <button type="button" className="ad-icon" onClick={feed.reload} aria-label="Refresh activity">
                <RefreshCw size={15} aria-hidden="true" />
              </button>
            </div>
          }
        >
          {feed.loading && !feed.data ? <Loading rows={8} /> : !activity.length ? (
            <Empty title="Nothing on this channel yet" hint="Switch the filter, or make a booking in chat to watch it land here." />
          ) : (
            <ul className="ad-feed">
              {activity.slice(0, 16).map((a, i) => (
                <li key={`${a.day}${a.at}${a.ref}${i}`}>
                  <time dateTime={`${a.day}T${a.at}`}>
                    <b className="ad-num">{a.at.slice(0, 5)}</b>
                    <span>{new Date(a.day).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</span>
                  </time>
                  <Chip kind={a.channel === "staff" ? "work" : "plain"}>{a.channel}</Chip>
                  <p><strong>{ACTION[a.action] || a.action.replace(/_/g, " ")}</strong> {a.patient} · {a.summary}</p>
                  {a.ref && <code className="ad-code">{a.ref}</code>}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="ad-two">
        <Panel title="Waitlist offers" count={feed.data?.offers.length ?? undefined}>
          {feed.loading && !feed.data ? <Loading rows={3} /> : !feed.data?.offers.length ? (
            <Empty title="No offers out right now" hint="When a booking is cancelled, the freed slot is offered here within seconds." />
          ) : (
            <ul className="ad-rows">
              {feed.data.offers.map((o) => (
                <li key={o.code}>
                  <div><strong>{o.patient}</strong><span>{o.doctor} · {o.slot}</span></div>
                  {o.status === "open"
                    ? <Chip kind="work">{Math.ceil(o.seconds_left / 60)} min left</Chip>
                    : <Status value={o.status} />}
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Outbox" action={<span className="ad-panel-note">email real · SMS and WhatsApp simulated</span>}>
          {feed.loading && !feed.data ? <Loading rows={3} /> : !feed.data?.outbox.length ? (
            <Empty title="Outbox is clear" hint="Confirmations and reminders appear here as they are queued." />
          ) : (
            <ul className="ad-rows">
              {feed.data.outbox.slice(0, 8).map((n, i) => (
                <li key={`${n.template}${n.at}${i}`}>
                  <div>
                    <strong>{n.template.replace(/_/g, " ")}</strong>
                    <span>{n.channel === "voice_call" ? "reminder call" : n.channel} to {n.to} · {n.at}</span>
                  </div>
                  <Status value={n.status} />
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Right now">
        <dl className="ad-facts">
          <div><dt>Date</dt><dd>{sum.data?.date ?? "—"} {sum.data?.now ?? ""}</dd></div>
          <div><dt>Database</dt><dd>{sum.data?.db ?? "—"}</dd></div>
          <div><dt>Email</dt><dd>{sum.data?.email_mode ?? "—"}</dd></div>
          <div><dt>Registered patients</dt><dd className="ad-num">{k.patients ?? "—"}</dd></div>
          <div><dt>Open nurse alerts</dt><dd className="ad-num">{k.nurse_alerts_open ?? "—"}</dd></div>
          <div><dt>Emails sent today</dt><dd className="ad-num">{k.emails_sent ?? "—"}</dd></div>
        </dl>
      </Panel>
    </>
  );
}
