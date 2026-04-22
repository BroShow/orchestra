import { create } from "zustand";
import type { RunEvent } from "@orchestra/shared-types";

export type RunUiStatus =
  | "idle"
  | "connecting"
  | "streaming"
  | "awaiting_approval"
  | "complete"
  | "error";

export interface ApprovalPayload {
  tool: string;
  arguments: Record<string, unknown>;
  tool_call_id: string;
}

interface RunStore {
  events: RunEvent[];
  status: RunUiStatus;
  pendingApproval: ApprovalPayload | null;
  finalAnswer: string | null;
  errorMessage: string | null;

  reset: () => void;
  appendEvent: (e: RunEvent) => void;
  setStatus: (s: RunUiStatus) => void;
}

export const useRunStore = create<RunStore>((set) => ({
  events: [],
  status: "idle",
  pendingApproval: null,
  finalAnswer: null,
  errorMessage: null,

  reset: () =>
    set({
      events: [],
      status: "idle",
      pendingApproval: null,
      finalAnswer: null,
      errorMessage: null,
    }),

  appendEvent: (e) =>
    set((prev) => {
      // Skip duplicate events if an SSE reconnect replays already-seen seqs.
      if (prev.events.some((x) => x.seq === e.seq)) return prev;
      const events = [...prev.events, e].sort((a, b) => a.seq - b.seq);

      let status = prev.status;
      let pendingApproval = prev.pendingApproval;
      let finalAnswer = prev.finalAnswer;
      let errorMessage = prev.errorMessage;

      switch (e.type) {
        case "approval_required":
          status = "awaiting_approval";
          pendingApproval = {
            tool: (e.payload.tool as string) ?? "",
            arguments:
              (e.payload.arguments as Record<string, unknown>) ?? {},
            tool_call_id: (e.payload.tool_call_id as string) ?? "",
          };
          break;
        case "run_complete":
          status = "complete";
          pendingApproval = null;
          finalAnswer = (e.payload.final as string) ?? null;
          break;
        case "error":
          status = "error";
          errorMessage =
            (e.payload.message as string) ?? "unknown error";
          break;
        default:
          if (status === "idle" || status === "connecting") {
            status = "streaming";
          }
          // Clear pendingApproval as soon as a post-approval event arrives.
          if (pendingApproval && e.type === "tool_result") {
            pendingApproval = null;
          }
      }

      return { events, status, pendingApproval, finalAnswer, errorMessage };
    }),

  setStatus: (s) => set({ status: s }),
}));
