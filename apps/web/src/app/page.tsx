import { RunComposer } from "@/components/RunComposer";
import { RunList } from "@/components/RunList";

export default function Home() {
  return (
    <main className="max-w-5xl mx-auto px-6 py-10 grid grid-cols-1 md:grid-cols-[1fr_320px] gap-8">
      <section>
        <h1 className="text-2xl font-semibold mb-4">orchestra</h1>
        <p className="text-neutral-600 mb-6">
          Hand the agent a task. Watch it reason, call tools, and report back.
        </p>
        <RunComposer />
      </section>

      <aside>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500 mb-3">
          Recent runs
        </h2>
        <RunList />
      </aside>
    </main>
  );
}
