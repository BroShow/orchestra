import type { RunEvent, RunSummary } from "@orchestra/shared-types";

// All client-side API calls go through /api, which Next.js rewrites to the
// FastAPI backend (see next.config.ts). Keeps the browser same-origin.

export interface CreateRunResponse {
  thread_id: string;
  status: string;
}

export interface RunListResponse {
  runs: RunSummary[];
  total: number;
}

export interface RunSnapshot {
  thread_id: string;
  task: string;
  status: string;
  step_count: number;
  messages: Array<Record<string, unknown>>;
  pending_approval: {
    tool: string;
    arguments: Record<string, unknown>;
    tool_call_id: string;
  } | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export async function createRun(task: string): Promise<CreateRunResponse> {
  const resp = await fetch("/api/runs", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ task }),
  });
  if (!resp.ok) throw new Error(`createRun: ${resp.status} ${await resp.text()}`);
  return (await resp.json()) as CreateRunResponse;
}

export async function listRuns(limit = 50): Promise<RunListResponse> {
  const resp = await fetch(`/api/runs?limit=${limit}`);
  if (!resp.ok) throw new Error(`listRuns: ${resp.status}`);
  return (await resp.json()) as RunListResponse;
}

export async function getRun(threadId: string): Promise<RunSnapshot> {
  const resp = await fetch(`/api/runs/${threadId}`);
  if (!resp.ok) throw new Error(`getRun: ${resp.status}`);
  return (await resp.json()) as RunSnapshot;
}

export async function approveRun(
  threadId: string,
  decision: "approved" | "denied",
): Promise<void> {
  const resp = await fetch(`/api/runs/${threadId}/approve`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  if (!resp.ok) throw new Error(`approveRun: ${resp.status} ${await resp.text()}`);
}

export async function cancelRun(threadId: string): Promise<void> {
  const resp = await fetch(`/api/runs/${threadId}`, { method: "DELETE" });
  if (!resp.ok) throw new Error(`cancelRun: ${resp.status}`);
}

export function sseUrl(threadId: string): string {
  return `/api/runs/${threadId}/events`;
}

export type { RunEvent };
