"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRun } from "@/lib/api";

export function RunComposer() {
  const router = useRouter();
  const [task, setTask] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!task.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const { thread_id } = await createRun(task.trim());
      router.push(`/runs/${thread_id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <textarea
        value={task}
        onChange={(e) => setTask(e.target.value)}
        placeholder="What should the agent do?"
        rows={4}
        className="border border-neutral-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-neutral-400"
        disabled={busy}
      />
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={busy || !task.trim()}
          className="bg-neutral-900 text-white px-4 py-2 rounded disabled:opacity-50"
        >
          {busy ? "Starting…" : "Start run"}
        </button>
      </div>
      {err && <p className="text-red-600 text-sm">{err}</p>}
    </form>
  );
}
