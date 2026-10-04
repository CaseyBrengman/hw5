import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { AgentName, AuditEvent, Cash, Draft, PaymentApproval, Ticket, TicketDecision } from "./types";

const AGENTS: { key: AgentName; name: string; mark: string; role: string }[] = [
  { key: "boss", name: "Boss", mark: "B", role: "Routes & decides" },
  { key: "inventory", name: "Inventory", mark: "I", role: "Stock & vendors" },
  { key: "accounting", name: "Accounting", mark: "A", role: "Cash & approvals" },
  { key: "facilities", name: "Facilities", mark: "F", role: "Leases & rent" },
  { key: "customer_service", name: "Customer Service", mark: "C", role: "Drafts replies" },
];
const AGENT = Object.fromEntries(AGENTS.map((a) => [a.key, a])) as Record<AgentName, (typeof AGENTS)[number]>;

const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price override",
};

const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
const time = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });
const prettyStatus = (s: string) => s.replace(/_/g, " ");

function parseArgs(args: unknown): Record<string, unknown> {
  if (typeof args === "string") {
    try {
      return JSON.parse(args);
    } catch {
      return { args };
    }
  }
  return (args as Record<string, unknown>) ?? {};
}

function brief(value: unknown, max = 160): string {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

/** Turn raw audit events into readable lines for the floor. */
function toLine(e: AuditEvent): { kind: string; title: string; body?: string } | null {
  const d = e.detail as Record<string, any>;
  switch (e.event) {
    case "run_start":
      return e.depth === 0
        ? { kind: "start", title: "Opens the ticket" }
        : { kind: "start", title: "Takes the assignment", body: d.task };
    case "model_response":
      return d.text ? { kind: "speech", title: "", body: d.text } : null;
    case "tool_call": {
      if (d.tool === "delegate" || d.tool === "final_result") return null;
      const args = parseArgs(d.args);
      const shown = Object.entries(args)
        .filter(([k]) => !["body", "reason", "note"].includes(k))
        .map(([k, v]) => `${k} ${brief(v, 40)}`)
        .join(" · ");
      return { kind: "tool", title: d.tool, body: shown };
    }
    case "tool_result":
      if (d.tool === "delegate" || d.tool === "final_result") return null;
      return { kind: "result", title: `${d.tool} returned`, body: brief(d.output, 220) };
    case "delegation":
      return { kind: "handoff", title: `Hands to ${AGENT[d.to_agent as AgentName]?.name ?? d.to_agent}`, body: d.task };
    case "delegation_refused":
      return { kind: "warn", title: `Hand-off to ${d.to_agent} declined`, body: d.reason };
    case "retry":
      return { kind: "warn", title: "Corrects course", body: brief(d.content, 200) };
    case "run_end": {
      const out = parseArgs(d.output) as Record<string, any>;
      return { kind: "end", title: e.depth === 0 ? "Final call" : "Reports back", body: out.decision ?? out.summary };
    }
    case "run_error":
      return { kind: "error", title: "Run stopped", body: `${d.error_type}: ${d.error}` };
  }
  return null;
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  // ?ticket=101 opens the board on that ticket (handy for links and screenshots)
  const [selected, setSelected] = useState<number | null>(() => {
    const t = Number(new URLSearchParams(window.location.search).get("ticket"));
    return Number.isFinite(t) && t > 0 ? t : null;
  });
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [cash, setCash] = useState<Cash | null>(null);
  const [cashFlash, setCashFlash] = useState(false);
  const [payments, setPayments] = useState<PaymentApproval[]>([]);
  const [pos, setPos] = useState<Draft[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [running, setRunning] = useState<number | null>(null);
  const [runStart, setRunStart] = useState<number | null>(null);
  const [lastDecision, setLastDecision] = useState<Record<number, TicketDecision>>({});
  const [operator, setOperator] = useState(() => localStorage.getItem("cc-operator") ?? "");
  const [notice, setNotice] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const [openDraft, setOpenDraft] = useState<string | null>(null);
  const floorRef = useRef<HTMLDivElement>(null);

  useEffect(() => localStorage.setItem("cc-operator", operator), [operator]);

  const flash = (tone: "ok" | "err", text: string) => {
    setNotice({ tone, text });
    window.setTimeout(() => setNotice(null), 6000);
  };

  const refreshCore = useCallback(async () => {
    try {
      const [t, c, a, d] = await Promise.all([api.tickets(), api.cash(), api.approvals(), api.drafts()]);
      setTickets(t);
      setCash((prev) => {
        if (prev && prev.balance !== c.balance) {
          setCashFlash(true);
          window.setTimeout(() => setCashFlash(false), 2400);
        }
        return c;
      });
      setPayments(a.payments);
      setPos(a.purchase_orders);
      setDrafts(d);
      setSelected((s) => s ?? t[0]?.id ?? null);
    } catch (err) {
      flash("err", `Can't reach the backend at localhost:8000. ${(err as Error).message}`);
    }
  }, []);

  const refreshEvents = useCallback(async (ticketId: number) => {
    try {
      const r = await api.events(ticketId);
      setEvents(r.events);
    } catch {
      /* the core refresh reports connection problems */
    }
  }, []);

  useEffect(() => {
    refreshCore();
  }, [refreshCore]);

  useEffect(() => {
    if (selected != null) refreshEvents(selected);
  }, [selected, refreshEvents]);

  // Poll while the team is working so the floor fills in live.
  useEffect(() => {
    if (running == null) return;
    const id = window.setInterval(() => {
      refreshEvents(running);
      api.approvals().then((a) => setPayments(a.payments)).catch(() => {});
    }, 1500);
    return () => window.clearInterval(id);
  }, [running, refreshEvents]);

  // Which run to show: the live one, or the most recent for this ticket.
  const runEvents = useMemo(() => {
    if (!events.length) return [];
    if (running != null && runStart != null) {
      const fresh = events.filter((e) => new Date(e.timestamp).getTime() >= runStart - 1000);
      const rid = fresh.find((e) => e.event === "run_start" && e.depth === 0)?.run_id;
      return rid ? fresh.filter((e) => e.run_id === rid) : fresh;
    }
    const lastRun = [...events].reverse().find((e) => e.event === "run_start" && e.depth === 0)?.run_id;
    return events.filter((e) => e.run_id === lastRun);
  }, [events, running, runStart]);

  useEffect(() => {
    if (running != null) floorRef.current?.scrollTo({ top: floorRef.current.scrollHeight, behavior: "smooth" });
  }, [runEvents.length, running]);

  const ticket = tickets.find((t) => t.id === selected) ?? null;

  const decision: TicketDecision | null = useMemo(() => {
    if (selected != null && lastDecision[selected] && running == null) return lastDecision[selected];
    const end = [...runEvents].reverse().find((e) => e.event === "run_end" && e.depth === 0);
    if (!end) return null;
    const out = parseArgs((end.detail as Record<string, unknown>).output);
    return out as unknown as TicketDecision;
  }, [runEvents, lastDecision, selected, running]);

  const roster = useMemo(() => {
    return AGENTS.map((a) => {
      const mine = runEvents.filter((e) => e.agent === a.key);
      const starts = mine.filter((e) => e.event === "run_start").length;
      const ends = mine.filter((e) => e.event === "run_end" || e.event === "run_error").length;
      const tools = mine.filter((e) => e.event === "tool_call" && !["delegate", "final_result"].includes(String(e.detail.tool))).length;
      const lastLine = [...mine].reverse().map(toLine).find((l) => l && (l.body || l.title));
      const state = starts === 0 ? "idle" : starts > ends ? "working" : "done";
      return { ...a, state, tools, lastLine };
    });
  }, [runEvents]);

  const tokens = useMemo(() => {
    const end = [...runEvents].reverse().find((e) => e.event === "run_end" && e.depth === 0);
    return end?.tokens ?? null;
  }, [runEvents]);

  async function startRun(t: Ticket) {
    setSelected(t.id);
    setRunning(t.id);
    setRunStart(Date.now());
    setLastDecision((d) => {
      const next = { ...d };
      delete next[t.id];
      return next;
    });
    try {
      const r = await api.runTicket(t.id);
      setLastDecision((d) => ({ ...d, [t.id]: r.decision }));
      flash("ok", `Ticket ${t.id} finished: ${prettyStatus(r.decision.final_status)}.`);
    } catch (err) {
      flash("err", (err as Error).message);
    } finally {
      await refreshEvents(t.id);
      setRunning(null);
      setRunStart(null);
      refreshCore();
    }
  }

  function requireName(): string | null {
    if (!operator.trim()) {
      flash("err", "Enter your name in the header before approving or resolving.");
      return null;
    }
    return operator.trim();
  }

  async function decidePayment(p: PaymentApproval | Draft, approve: boolean) {
    const name = requireName();
    if (!name) return;
    const id = "approval_id" in p ? p.approval_id : p.draft_id;
    try {
      if (approve) {
        const r = await api.approve(id, name);
        if (r.payment && !r.payment.paid) flash("err", `Approved, but payment refused: ${r.payment.error}`);
        else flash("ok", `${id} approved by ${name}${r.payment ? " and paid" : ""}.`);
      } else {
        await api.deny(id, name);
        flash("ok", `${id} declined by ${name}.`);
      }
    } catch (err) {
      flash("err", (err as Error).message);
    }
    refreshCore();
  }

  async function resolve(t: Ticket) {
    const name = requireName();
    if (!name) return;
    try {
      await api.resolveTicket(t.id, name);
      flash("ok", `Ticket ${t.id} marked resolved.`);
    } catch (err) {
      flash("err", (err as Error).message);
    }
    refreshCore();
  }

  async function reset() {
    if (!window.confirm("Reset the working database to its original values? Drafts and approvals are cleared; the audit trail is kept.")) return;
    try {
      await api.reset();
      setLastDecision({});
      flash("ok", "Database restored to its original state.");
    } catch (err) {
      flash("err", (err as Error).message);
    }
    refreshCore();
  }

  const pending = payments.filter((p) => p.status === "pending");
  const settled = payments.filter((p) => p.status !== "pending");
  const pendingPos = pos.filter((p) => p.status.startsWith("draft"));
  const ticketDrafts = drafts.filter((d) => d.ticket_id === selected);
  const runFinished = running == null && runEvents.some((e) => e.event === "run_end" && e.depth === 0);

  return (
    <div className="shell">
      <header className="masthead">
        <div className="brand">
          <span className="eyebrow">Campus Customs</span>
          <h1>The Agent Desk</h1>
        </div>
        <div className="masthead-meta">
          <label className="operator">
            <span>Operator</span>
            <input value={operator} onChange={(e) => setOperator(e.target.value)} placeholder="Your name" />
          </label>
          <div className={`balance ${cashFlash ? "flash" : ""}`}>
            <span className="eyebrow">Checking</span>
            <strong>{cash ? money(cash.balance) : "—"}</strong>
            <span className="asof">as of {cash?.as_of ?? "—"}</span>
          </div>
        </div>
      </header>

      {notice && <div className={`notice ${notice.tone}`}>{notice.text}</div>}

      <main className="grid">
        {/* ---------- Docket ---------- */}
        <section className="col docket">
          <div className="col-head">
            <h2>Docket</h2>
            <span className="count">{tickets.filter((t) => t.is_open).length} open</span>
          </div>
          {tickets.map((t) => (
            <button
              key={t.id}
              className={`ticket ${selected === t.id ? "selected" : ""} ${t.state}`}
              onClick={() => setSelected(t.id)}
            >
              <div className="ticket-top">
                <span className="no">No. {t.id}</span>
                <span className={`status s-${t.status}`}>{t.state === "resolved" ? "Resolved" : prettyStatus(t.status)}</span>
              </div>
              <div className="ticket-subject">{t.subject}</div>
              <div className="ticket-meta">
                {TYPE_LABEL[t.type] ?? t.type} · {t.requester}
              </div>
              {running === t.id && <div className="working-bar" />}
            </button>
          ))}
          <button className="text-btn reset" onClick={reset} disabled={running != null}>
            Reset to original data
          </button>
        </section>

        {/* ---------- Floor ---------- */}
        <section className="col floor">
          {ticket ? (
            <>
              <div className="ticket-hero">
                <div>
                  <span className="eyebrow">
                    {TYPE_LABEL[ticket.type] ?? ticket.type} · Ticket {ticket.id}
                  </span>
                  <h2 className="hero-title">{ticket.subject}</h2>
                  <dl className="facts">
                    <div><dt>Requester</dt><dd>{ticket.requester}</dd></div>
                    {ticket.sku && <div><dt>Item</dt><dd>{ticket.sku} · {ticket.size} · ×{ticket.qty}</dd></div>}
                    {ticket.invoice_id && <div><dt>Invoice</dt><dd>{ticket.invoice_id}</dd></div>}
                    {ticket.lease_id && <div><dt>Lease</dt><dd>{ticket.lease_id}</dd></div>}
                    <div><dt>Status</dt><dd>{prettyStatus(ticket.status)}</dd></div>
                  </dl>
                </div>
                <div className="hero-actions">
                  <button
                    className="primary"
                    disabled={running != null || ticket.state === "resolved"}
                    onClick={() => startRun(ticket)}
                  >
                    {running === ticket.id ? "Team at work…" : runFinished ? "Run again" : "Begin run"}
                  </button>
                  {runFinished && ticket.state !== "resolved" && (
                    <button className="secondary" onClick={() => resolve(ticket)}>
                      Mark resolved
                    </button>
                  )}
                </div>
              </div>

              <div className="roster">
                {roster.map((a) => (
                  <div key={a.key} className={`agent-card a-${a.key} ${a.state}`}>
                    <div className="agent-top">
                      <span className="mark">{a.mark}</span>
                      <div>
                        <div className="agent-name">{a.name}</div>
                        <div className="agent-role">{a.role}</div>
                      </div>
                      <span className={`dot ${a.state}`} title={a.state} />
                    </div>
                    <div className="agent-last">
                      {a.state === "idle" ? <em>Not called</em> : a.lastLine?.body ? brief(a.lastLine.body, 90) : a.lastLine?.title}
                    </div>
                  </div>
                ))}
              </div>

              <div className="floor-head">
                <h3>The Floor</h3>
                <span className="count">
                  {runEvents.length ? `${runEvents.length} steps` : "No run yet"}
                  {tokens ? ` · ${(tokens.ticket_total_input + tokens.ticket_total_output).toLocaleString()} tokens` : ""}
                </span>
              </div>
              <div className="feed" ref={floorRef}>
                {runEvents.length === 0 && (
                  <p className="empty">Select <em>Begin run</em> and the team’s conversation will appear here as it happens.</p>
                )}
                {runEvents.map((e, i) => {
                  const line = toLine(e);
                  if (!line) return null;
                  const a = AGENT[e.agent];
                  return (
                    <div key={i} className={`line k-${line.kind} a-${e.agent}`} style={{ marginLeft: `${e.depth * 28}px` }}>
                      <span className="mark small">{a.mark}</span>
                      <div className="line-body">
                        <div className="line-head">
                          <span className="who">{a.name}</span>
                          {line.title && <span className="what">{line.title}</span>}
                          <span className="when">{time(e.timestamp)}</span>
                        </div>
                        {line.body && <div className="line-text">{line.body}</div>}
                      </div>
                    </div>
                  );
                })}
                {running != null && <div className="typing"><span /><span /><span /></div>}
              </div>
            </>
          ) : (
            <p className="empty">Loading tickets…</p>
          )}
        </section>

        {/* ---------- Ledger ---------- */}
        <aside className="col ledger">
          <div className="col-head"><h2>Awaiting You</h2><span className="count">{pending.length + pendingPos.length}</span></div>
          {pending.length === 0 && pendingPos.length === 0 && <p className="empty small">Nothing needs a signature.</p>}
          {pending.map((p) => (
            <div key={p.approval_id} className="approval">
              <div className="approval-top">
                <span className="no">{p.approval_id}</span>
                <span className="amount">{money(p.amount)}</span>
              </div>
              <div className="approval-what">
                {p.kind === "rent" ? `Rent · lease ${p.ref_id}` : `Invoice ${p.ref_id}`} · ticket {p.ticket_id}
              </div>
              <p className="approval-why">{p.reason}</p>
              {cash && p.amount > cash.balance && <p className="warn-text">Exceeds the checking balance; payment will be refused.</p>}
              <div className="approval-actions">
                <button className="primary small" onClick={() => decidePayment(p, true)}>Approve & pay</button>
                <button className="text-btn" onClick={() => decidePayment(p, false)}>Decline</button>
              </div>
            </div>
          ))}
          {pendingPos.map((p) => (
            <div key={p.draft_id} className="approval">
              <div className="approval-top">
                <span className="no">{p.draft_id}</span>
                <span className="amount">{money(p.total_cost ?? 0)}</span>
              </div>
              <div className="approval-what">
                Purchase order · {p.vendor_name} · {p.sku} {p.size} ×{p.qty}
              </div>
              <div className="approval-actions">
                <button className="primary small" onClick={() => decidePayment(p, true)}>Approve</button>
                <button className="text-btn" onClick={() => decidePayment(p, false)}>Reject</button>
              </div>
            </div>
          ))}

          <div className="col-head spaced"><h2>Summary</h2></div>
          {decision ? (
            <div className="summary">
              <p className="verdict">{decision.decision}</p>
              <div className="summary-row"><span>Outcome</span><strong>{prettyStatus(decision.final_status)}</strong></div>
              <div className="summary-row"><span>Team</span><strong>{decision.assigned_agents.map((a) => AGENT[a]?.name ?? a).join(", ") || "Boss alone"}</strong></div>
              {roster.filter((a) => a.state !== "idle").map((a) => (
                <div key={a.key} className="summary-row"><span>{a.name}</span><strong>{a.tools} tool {a.tools === 1 ? "call" : "calls"}</strong></div>
              ))}
              {decision.actions_taken.length > 0 && (
                <ul className="actions">{decision.actions_taken.map((x, i) => <li key={i}>{x}</li>)}</ul>
              )}
              {decision.needs_human.length > 0 && (
                <div className="needs"><span className="eyebrow">Needs a human</span>{decision.needs_human.map((x, i) => <p key={i}>{x}</p>)}</div>
              )}
            </div>
          ) : (
            <p className="empty small">The summary appears when the Boss makes the final call.</p>
          )}

          {ticketDrafts.length > 0 && (
            <>
              <div className="col-head spaced"><h2>Drafts</h2><span className="count">never sent</span></div>
              {ticketDrafts.map((d) => (
                <div key={d.draft_id} className="draft">
                  <button className="draft-head" onClick={() => setOpenDraft(openDraft === d.draft_id ? null : d.draft_id)}>
                    <span className="no">{d.draft_id}</span>
                    <span>{d.kind === "customer_message" ? d.subject : `PO · ${d.vendor_name}`}</span>
                  </button>
                  {openDraft === d.draft_id && d.body && <pre className="draft-body">To: {d.to}{"\n\n"}{d.body}</pre>}
                </div>
              ))}
            </>
          )}

          <div className="col-head spaced"><h2>Ledger</h2></div>
          {settled.length === 0 ? (
            <p className="empty small">No payment decisions yet.</p>
          ) : (
            <table className="ledger-table">
              <tbody>
                {settled.map((p) => (
                  <tr key={p.approval_id}>
                    <td>{p.approval_id}<span className="sub">{p.kind === "rent" ? "Rent" : `Invoice ${p.ref_id}`} · {p.decided_by}</span></td>
                    <td className={`num ${p.status}`}>{p.status === "paid" ? `−${money(p.amount)}` : p.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </aside>
      </main>
    </div>
  );
}
