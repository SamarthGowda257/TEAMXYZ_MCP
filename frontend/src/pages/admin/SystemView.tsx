import { Empty, Loading, Panel, Table, useOps, type Col } from "../adminKit";

/** System — the context blackboard, the event bus, search, and how long each MCP tool is taking. */

type SystemInfo = {
  blackboard: { backend: string; patients_in_memory: number; cache_hit_rate: number | null; hits: number; misses: number; last_error: string | null };
  events: {
    backend: string; published: number; processed: number; failed: number; dead_lettered: number;
    lag_ms_last: number; worker_alive: boolean; pending?: number; dlq_length?: number;
    by_type?: Record<string, number>;
  };
  search?: { mode: string; docs: number; kb_total: number; pgvector: boolean; embeddings?: { provider: string; model: string | null } };
};
type Metrics = {
  tools: { tool: string; count: number; errors: number; p50_ms: number; p95_ms: number }[];
  p50_ms: number; p95_ms: number; total_calls: number; uptime_s: number;
};
type Integrations = {
  email: { transport: string; from: string; demo_override: boolean };
  google: { connected: boolean };
  calendar: { google_connected: boolean; calendar_id: string; last_error: string | null };
  payments: { provider: string; webhook: boolean };
};

function uptime(s: number | undefined) {
  if (!s) return "—";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h} h ${m} min` : `${m} min`;
}

export function SystemView() {
  const sys = useOps<SystemInfo>("/api/ops/system", 20000);
  const met = useOps<Metrics>("/api/metrics", 15000);
  const integ = useOps<Integrations>("/api/ops/integrations", 60000);
  const b = sys.data?.blackboard;
  const e = sys.data?.events;
  const m = met.data;

  const cols: Col<Metrics["tools"][number]>[] = [
    { key: "t", head: "Tool", cell: (t) => <code className="ad-code">{t.tool}</code> },
    { key: "n", head: "Calls", num: true, cell: (t) => <span className="ad-num">{t.count}</span> },
    { key: "e", head: "Errors", num: true, cell: (t) => <span className={t.errors ? "ad-num ad-bad" : "ad-num"}>{t.errors}</span> },
    { key: "p50", head: "p50", num: true, cell: (t) => <span className="ad-num">{t.p50_ms} ms</span> },
    {
      key: "p95", head: "p95", num: true,
      cell: (t) => <span className={t.p95_ms > 1200 ? "ad-num ad-warnnum" : "ad-num"}>{t.p95_ms} ms</span>,
    },
  ];

  return (
    <div className="ad-stack">
      <ul className="ad-kpis">
        <li className="ad-kpi">
          <span className="ad-kpi-label">Context cache hit rate</span>
          <strong className="ad-kpi-value">{b?.cache_hit_rate != null ? `${Math.round(b.cache_hit_rate * 100)}%` : "—"}</strong>
          <span className="ad-kpi-sub">{b ? `${b.hits} hits · ${b.misses} misses` : "warming up"}</span>
        </li>
        <li className="ad-kpi">
          <span className="ad-kpi-label">Patients in working memory</span>
          <strong className="ad-kpi-value">{b?.patients_in_memory ?? "—"}</strong>
          <span className="ad-kpi-sub">{b?.backend || "—"}</span>
        </li>
        <li className="ad-kpi">
          <span className="ad-kpi-label">Events processed</span>
          <strong className="ad-kpi-value">{e?.processed ?? "—"}</strong>
          <span className="ad-kpi-sub">{e ? `of ${e.published} published · lag ${e.lag_ms_last} ms` : ""}</span>
        </li>
        <li className={e && (e.dead_lettered || e.failed) ? "ad-kpi ad-kpi-alert" : "ad-kpi"}>
          <span className="ad-kpi-label">Pending / dead-lettered</span>
          <strong className="ad-kpi-value">{e ? `${e.pending ?? 0} / ${e.dlq_length ?? e.dead_lettered}` : "—"}</strong>
          <span className="ad-kpi-sub">{e?.worker_alive ? "workers running" : "workers stalled"}</span>
        </li>
      </ul>

      <Panel title="Tool latency" action={<span className="ad-panel-note">server time per MCP tool · uptime {uptime(m?.uptime_s)}</span>}>
        {met.loading && !met.data ? <Loading rows={6} />
          : met.error ? <Empty title="Could not read the metrics" hint={met.error} />
          : !m?.tools.length ? (
            <Empty title="No tool calls since the server started"
                   hint="Latency appears the moment a Talkdesk agent calls a tool. This is a cold counter, not an error." />
          ) : (
            <>
              <p className="ad-note">
                Across all tools: p50 {Math.round(m.p50_ms)} ms, p95 {Math.round(m.p95_ms)} ms, {m.total_calls} calls.
              </p>
              <Table cols={cols} rows={m.tools.slice(0, 20)} rowKey={(t) => t.tool} />
            </>
          )}
      </Panel>

      <div className="ad-two">
        <Panel title="Blackboard and events">
          <dl className="ad-facts">
            <div><dt>Blackboard backend</dt><dd>{b?.backend ?? "—"}</dd></div>
            <div><dt>Event backend</dt><dd>{e?.backend ?? "—"}</dd></div>
            <div><dt>Failed</dt><dd className="ad-num">{e?.failed ?? "—"}</dd></div>
            <div><dt>Dead-lettered</dt><dd className="ad-num">{e?.dead_lettered ?? "—"}</dd></div>
            <div><dt>Last blackboard error</dt><dd>{b?.last_error || "none"}</dd></div>
          </dl>
          {!!e?.by_type && Object.keys(e.by_type).length > 0 && (
            <ul className="ad-rows">
              {Object.entries(e.by_type).map(([t, n]) => (
                <li key={t}><div><strong>{t.replace(/_/g, " ")}</strong></div><span className="ad-num">{n}</span></li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Search and integrations">
          <dl className="ad-facts">
            <div><dt>Search mode</dt><dd>{sys.data?.search?.mode ?? "—"}</dd></div>
            <div><dt>Indexed passages</dt><dd className="ad-num">{sys.data?.search?.kb_total ?? "—"}</dd></div>
            <div><dt>Embeddings</dt><dd>{sys.data?.search?.embeddings?.provider ?? "none"}</dd></div>
            <div><dt>Email transport</dt><dd>{integ.data?.email.transport ?? "—"}</dd></div>
            <div><dt>Sends from</dt><dd>{integ.data?.email.from ?? "—"}</dd></div>
            <div><dt>Google calendar</dt><dd>{integ.data?.calendar.google_connected ? "connected" : "not connected"}</dd></div>
            <div><dt>Payments</dt><dd>{integ.data?.payments.provider ?? "—"}</dd></div>
          </dl>
          {integ.data?.calendar.last_error && <p className="ad-note">Calendar: {integ.data.calendar.last_error}</p>}
        </Panel>
      </div>
    </div>
  );
}
