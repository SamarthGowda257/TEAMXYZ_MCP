import { useState } from "react";
import { Info } from "lucide-react";
import {
  Chip, Empty, Filters, Loading, Mini, Panel, SearchBox, Status, Table, when, useOps, type Col,
} from "../adminKit";

/**
 * Conversations — the summary the bot saved at the end of each chat or call.
 *
 * This is not a transcript and it is never presented as one: Talkdesk keeps the wording. What is
 * stored here is one honest sentence per conversation, plus its outcome. Open a patient's record
 * to see that summary beside every action the AI actually took.
 */

type Convo = {
  id: number; channel: string; summary: string; topics: string; outcome: string;
  created_at: string; phone: string; full_name: string; patient_id: number | null; escalated: boolean;
};
type Resp = { total: number; by_channel: Record<string, number>; conversations: Convo[] };

export function Conversations({ onPatient }: { onPatient: (id: number) => void }) {
  const [channel, setChannel] = useState("");
  const [q, setQ] = useState("");
  const { data, loading, error } = useOps<Resp>(`/api/ops/conversations?limit=120${channel ? `&channel=${channel}` : ""}`, 25000);

  const term = q.trim().toLowerCase();
  const rows = (data?.conversations || []).filter((c) =>
    !term || `${c.full_name} ${c.phone} ${c.summary} ${c.topics}`.toLowerCase().includes(term));

  const cols: Col<Convo>[] = [
    { key: "w", head: "When", cell: (c) => when(c.created_at) },
    { key: "ch", head: "Channel", cell: (c) => <Chip kind="plain">{c.channel || "chat"}</Chip> },
    { key: "p", head: "Patient", cell: (c) => <>{c.full_name || "Caller"}<span className="ad-sub ad-num">{c.phone}</span></> },
    {
      key: "s", head: "What the bot recorded", wide: true,
      cell: (c) => (
        <>
          {c.summary}
          {c.topics && <span className="ad-sub">{c.topics.split(",").map((t) => t.trim()).join(" · ")}</span>}
        </>
      ),
    },
    {
      key: "o", head: "Outcome",
      cell: (c) => (c.escalated ? <Chip kind="urgent">escalated</Chip> : <Status value={c.outcome || "resolved"} />),
    },
    {
      key: "do", head: "Record", width: "1%",
      cell: (c) => (c.patient_id
        ? <Mini tone="accent" onClick={() => onPatient(c.patient_id!)}>Open record</Mini>
        : <span className="ad-dim">not registered</span>),
    },
  ];

  return (
    <Panel
      title="Conversations"
      count={data ? rows.length : undefined}
      action={
        <div className="ad-head-tools">
          <Filters label="Channel" value={channel} onChange={setChannel}
                   options={[["", "All"], ["chat", "Chat"], ["voice", "Voice"], ["web", "Web"]]} />
          <SearchBox value={q} onChange={setQ} placeholder="Name, number, topic" label="Filter conversations" />
        </div>
      }
    >
      <div className="ad-truth">
        <Info size={16} aria-hidden="true" />
        <p>
          <strong>Summaries, not transcripts.</strong> Talkdesk does not send chat or voice transcripts to
          WellNest, so there is nothing verbatim to show and nothing is invented here. Each line is the note
          the bot wrote when the conversation ended. The words themselves live in Talkdesk Conversations.
        </p>
      </div>
      {data && (
        <p className="ad-note">
          {Object.entries(data.by_channel).map(([c, n]) => `${n} on ${c}`).join(" · ") || "no conversations recorded yet"}
        </p>
      )}
      {loading && !data ? <Loading rows={10} />
        : error ? <Empty title="Could not load conversations" hint={error} />
        : !rows.length ? (
          <Empty title="No conversations match"
                 hint="The AI saves a note whenever a conversation changes something. Run a chat and it appears here." />
        ) : <Table cols={cols} rows={rows} rowKey={(c) => String(c.id)} />}
    </Panel>
  );
}
