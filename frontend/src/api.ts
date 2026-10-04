import type { AuditEvent, Cash, Draft, PaymentApproval, Ticket, TicketDecision } from "./types";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  tickets: () => request<Ticket[]>("/tickets"),
  runTicket: (id: number) =>
    request<{ run_id: string; decision: TicketDecision }>(`/tickets/${id}/run`, { method: "POST" }),
  resolveTicket: (id: number, resolved_by: string) =>
    request(`/tickets/${id}/resolve`, { method: "POST", body: JSON.stringify({ resolved_by }) }),
  events: (ticketId: number, limit = 300) =>
    request<{ total: number; events: AuditEvent[] }>(`/events?ticket_id=${ticketId}&limit=${limit}`),
  approvals: () =>
    request<{ payments: PaymentApproval[]; purchase_orders: Draft[] }>("/approvals"),
  approve: (id: string, approved_by: string) =>
    request<{ payment?: { paid: boolean; error?: string } }>(`/approvals/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved_by }),
    }),
  deny: (id: string, approved_by: string) =>
    request(`/approvals/${id}/deny`, { method: "POST", body: JSON.stringify({ approved_by }) }),
  cash: () => request<Cash>("/cash"),
  drafts: () => request<Draft[]>("/drafts"),
  reset: () => request<{ reset: boolean }>("/reset", { method: "POST" }),
};
