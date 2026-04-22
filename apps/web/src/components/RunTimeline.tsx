"use client";

import { useEffect, useRef } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { sseUrl } from "@/lib/api";
import { useRunStore } from "@/lib/store";
import type { RunEvent, RunEventType } from "@orchestra/shared-types";
import { ApprovalCard } from "./ApprovalCard";

function useLiveRun(threadId: string) {
  const appendEvent = useRunStore((s) => s.appendEvent);
  const reset = useRunStore((s) => s.reset);
  const setStatus = useRunStore((s) => s.setStatus);
  const mounted = useRef(false);

  useEffect(() => {
    reset();
    setStatus("connecting");
    const controller = new AbortController();

    fetchEventSource(sseUrl(threadId), {
      signal: controller.signal,
      openWhenHidden: true,
      onopen: async (r) => {
        if (!r.ok) throw new Error(`SSE open: ${r.status}`);
      },
      onmessage: (msg) => {
        if (!msg.event) return;
        try {
          const data = JSON.parse(msg.data) as {
            thread_id: string;
            seq: number;
            payload: Record<string, unknown>;
          };
          const ev: RunEvent = {
            type: msg.event as RunEventType,
            thread_id: data.thread_id,
            seq: data.seq,
            payload: data.payload,
          };
          appendEvent(ev);
        } catch {
          // ignore malformed events
        }
      },
      onerror: (e) => {
        // fetch-event-source retries automatically unless we throw.
        console.warn("SSE error", e);
      },
    });

    mounted.current = true;
    return () => controller.abort();
  }, [threadId, appendEvent, reset, setStatus]);
}

function EventRow({ event }: { event: RunEvent }) {
  const { type, payload } = event;
  if (type === "step_start") {
    return (
      <div className="text-xs text-neutral-500 uppercase tracking-wide py-1 border-b border-neutral-200">
        Step → {(payload.node as string) ?? "?"}
      </div>
    );
  }
  if (type === "model_chunk") {
    return (
      <div className="py-1 whitespace-pre-wrap">
        {(payload.text as string) ?? ""}
      </div>
    );
  }
  if (type === "tool_call_requested") {
    return (
      <div className="my-2 p-2 border border-neutral-300 rounded bg-white">
        <div className="text-xs text-neutral-600 mb-1">
          Tool call: <span className="mono">{payload.tool as string}</span>
        </div>
        <pre className="mono text-xs bg-neutral-50 p-1 rounded overflow-x-auto">
          {JSON.stringify(payload.arguments, null, 2)}
        </pre>
      </div>
    );
  }
  if (type === "tool_result") {
    const denied = Boolean(payload.denied);
    return (
      <details className="my-1">
        <summary
          className={`cursor-pointer text-xs ${denied ? "text-amber-700" : "text-green-700"}`}
        >
          {denied ? "Tool denied" : "Tool result"}
        </summary>
        <pre className="mono text-xs bg-neutral-50 border border-neutral-200 rounded p-2 mt-1 overflow-x-auto">
          {String(payload.content ?? "")}
        </pre>
      </details>
    );
  }
  if (type === "step_end") {
    return <div className="h-1" />;
  }
  if (type === "run_complete") {
    return (
      <div className="mt-3 p-3 border-2 border-green-400 bg-green-50 rounded">
        <h3 className="font-semibold text-green-900 mb-1">Final answer</h3>
        <p className="whitespace-pre-wrap">{payload.final as string}</p>
      </div>
    );
  }
  if (type === "error") {
    return (
      <div className="mt-3 p-3 border-2 border-red-400 bg-red-50 rounded">
        <h3 className="font-semibold text-red-900 mb-1">Error</h3>
        <p>{payload.message as string}</p>
      </div>
    );
  }
  return null;
}

export function RunTimeline({ threadId }: { threadId: string }) {
  useLiveRun(threadId);
  const events = useRunStore((s) => s.events);
  const status = useRunStore((s) => s.status);
  const pendingApproval = useRunStore((s) => s.pendingApproval);

  return (
    <div aria-live="polite">
      <div className="text-xs text-neutral-500 mb-2">
        status: <span className="mono">{status}</span>
      </div>
      {events.map((e) => (
        <EventRow key={e.seq} event={e} />
      ))}
      {pendingApproval && (
        <div className="mt-3">
          <ApprovalCard threadId={threadId} payload={pendingApproval} />
        </div>
      )}
      {events.length === 0 && status !== "idle" && (
        <p className="text-neutral-500 text-sm">Waiting for the agent…</p>
      )}
    </div>
  );
}
