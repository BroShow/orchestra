"use client";

import { useState } from "react";
import { approveRun } from "@/lib/api";
import type { ApprovalPayload } from "@/lib/store";

export function ApprovalCard({
  threadId,
  payload,
}: {
  threadId: string;
  payload: ApprovalPayload;
}) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<"approved" | "denied" | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function decide(decision: "approved" | "denied") {
    setBusy(true);
    setErr(null);
    try {
      await approveRun(threadId, decision);
      setDone(decision);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border-2 border-amber-400 bg-amber-50 rounded px-4 py-3">
      <h3 className="font-semibold text-amber-900 mb-2">
        Approval required
      </h3>
      <p className="text-sm mb-2">
        The agent wants to run tool <span className="mono font-semibold">{payload.tool}</span> with:
      </p>
      <pre className="mono bg-white border border-amber-200 rounded p-2 text-xs overflow-x-auto mb-3">
        {JSON.stringify(payload.arguments, null, 2)}
      </pre>
      {done ? (
        <p className="text-sm text-amber-900">
          You {done === "approved" ? "approved" : "denied"} this call.
        </p>
      ) : (
        <div className="flex gap-2">
          <button
            onClick={() => decide("approved")}
            disabled={busy}
            className="bg-amber-700 text-white px-3 py-1.5 rounded disabled:opacity-50"
          >
            Approve
          </button>
          <button
            onClick={() => decide("denied")}
            disabled={busy}
            className="border border-amber-700 text-amber-900 px-3 py-1.5 rounded disabled:opacity-50"
          >
            Deny
          </button>
        </div>
      )}
      {err && <p className="text-sm text-red-600 mt-2">{err}</p>}
    </div>
  );
}
