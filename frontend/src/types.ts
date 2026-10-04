export type AgentName = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: string;
  notes: string | null;
  created_at: string;
  is_open: boolean;
  state: "open" | "resolved";
}

export interface AuditEvent {
  timestamp: string;
  run_id: string;
  ticket_id: number | null;
  agent: AgentName;
  depth: number;
  chain: string[];
  step: number;
  event:
    | "run_start" | "model_response" | "tool_call" | "tool_result" | "retry"
    | "delegation" | "delegation_refused" | "run_end" | "run_error";
  detail: Record<string, unknown>;
  tokens: Record<string, number> | null;
}

export interface TicketDecision {
  ticket_id: number;
  assigned_agents: AgentName[];
  decision: string;
  final_status: string;
  actions_taken: string[];
  drafts_created: string[];
  approvals_requested: string[];
  needs_human: string[];
}

export interface PaymentApproval {
  approval_id: string;
  kind: "invoice" | "rent";
  ref_id: number;
  ticket_id: number;
  amount: number;
  reason: string;
  requested_by: string;
  requested_at: string;
  status: "pending" | "approved" | "denied" | "paid";
  decided_by: string | null;
  decided_at: string | null;
  payment_id?: number;
}

export interface Draft {
  draft_id: string;
  kind: "customer_message" | "purchase_order";
  status: string;
  ticket_id: number;
  to?: string;
  subject?: string;
  body?: string;
  vendor_name?: string;
  sku?: string;
  size?: string;
  qty?: number;
  total_cost?: number;
  expected_arrival?: string | null;
  decided_by?: string;
}

export interface Cash {
  account: string;
  balance: number;
  as_of: string;
}
