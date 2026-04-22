// Types shared between the Next.js web app and the FastAPI backend.
// The Python Pydantic models are the source of truth; these are the TS mirror.

export type RunEventType =
  | "step_start"
  | "model_chunk"
  | "tool_call_requested"
  | "approval_required"
  | "tool_result"
  | "step_end"
  | "run_complete"
  | "error";

export interface RunEvent {
  type: RunEventType;
  thread_id: string;
  seq: number;
  payload: Record<string, unknown>;
}

export type RunStatus =
  | "running"
  | "awaiting_approval"
  | "complete"
  | "error"
  | "cancelled";

export interface RunSummary {
  thread_id: string;
  task: string;
  status: RunStatus;
  step_count: number;
  created_at: string;
  updated_at: string;
}
