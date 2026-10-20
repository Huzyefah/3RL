import { Suspense } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { apiFetch } from "@/lib/upstream";
import type { IncidentDetail } from "@/lib/types";
import { IncidentView } from "@/components/IncidentView";

async function IncidentLoader({ params }: { params: PageProps<"/incidents/[id]">["params"] }) {
  const { id } = await params;
  let res: Response;
  try {
    res = await apiFetch(`/incidents/${encodeURIComponent(id)}`);
  } catch {
    return <LoadError id={id} reason="sentinel-api is unreachable" />;
  }
  if (res.status === 404) notFound();
  if (!res.ok) return <LoadError id={id} reason={`sentinel-api answered ${res.status}`} />;
  const detail = (await res.json()) as IncidentDetail;
  return <IncidentView initial={detail} />;
}

function LoadError({ id, reason }: { id: string; reason: string }) {
  return (
    <div data-testid="incident-error" className="rounded-xl border border-line bg-surface p-6 text-sm">
      <p className="font-semibold">Could not load {id}</p>
      <p className="mt-1 text-muted">{reason}. The live stream keeps running; retry in a moment.</p>
      <Link href="/" className="mt-3 inline-block text-accent-ink hover:underline">
        ← Back to Live Ops
      </Link>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="flex animate-pulse flex-col gap-4" aria-busy>
      <div className="h-28 rounded-xl border border-line bg-surface" />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="h-96 rounded-xl border border-line bg-surface lg:col-span-2" />
        <div className="h-96 rounded-xl border border-line bg-surface" />
      </div>
    </div>
  );
}

export default function IncidentPage({ params }: PageProps<"/incidents/[id]">) {
  return (
    <Suspense fallback={<Skeleton />}>
      <IncidentLoader params={params} />
    </Suspense>
  );
}
