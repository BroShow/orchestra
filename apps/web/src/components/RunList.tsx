"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listRuns } from "@/lib/api";
import type { RunSummary } from "@orchestra/shared-types";

function statusBadge(status: string) {
  const color =
    status === "running"
      ? "bg-blue-100 text-blue-800"
      : status === "awaiting_approval"
        ? "bg-amber-100 text-amber-800"
        : status === "complete"
          ? "bg-green-100 text-green-800"
          : status === "error"
            ? "bg-red-100 text-red-800"
            : "bg-neutral-100 text-neutral-600";
  return `text-xs px-2 py-0.5 rounded ${color}`;
}

export function RunList() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const tick = async () => {
      try {
        const data = await listRuns();
        if (live) setRuns(data.runs);
      } catch (e) {
        if (live) setErr(e instanceof Error ? e.message : String(e));
      }
    };
    tick();
    const iv = setInterval(tick, 3000);
    return () => {
      live = false;
      clearInterval(iv);
    };
  }, []);

  if (err) return <p className="text-sm text-red-600">{err}</p>;
  if (runs.length === 0)
    return <p className="text-sm text-neutral-500">No runs yet.</p>;

  return (
    <ul className="flex flex-col gap-2">
      {runs.map((r) => (
        <li key={r.thread_id}>
          <Link
            href={`/runs/${r.thread_id}`}
            className="block border border-neutral-200 rounded px-3 py-2 hover:bg-neutral-100"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="mono text-xs text-neutral-600">
                {r.thread_id.slice(0, 16)}…
              </span>
              <span className={statusBadge(r.status)}>{r.status}</span>
            </div>
            <p className="text-sm text-neutral-900 line-clamp-2">{r.task}</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
