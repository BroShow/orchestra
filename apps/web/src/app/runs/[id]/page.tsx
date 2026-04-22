import Link from "next/link";
import { RunTimeline } from "@/components/RunTimeline";

type Params = { id: string };

export default async function RunDetailPage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { id } = await params;

  return (
    <main className="max-w-4xl mx-auto px-6 py-10">
      <Link
        href="/"
        className="text-sm text-neutral-500 hover:text-neutral-900"
      >
        ← all runs
      </Link>
      <h1 className="text-xl font-semibold mt-2 mb-6">
        Run <span className="mono text-sm text-neutral-500">{id}</span>
      </h1>
      <RunTimeline threadId={id} />
    </main>
  );
}
