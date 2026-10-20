"use client";
import Link from "next/link";
import { useState } from "react";
import { AlertOctagon, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { post } from "@/lib/use-poll";
import type { Status } from "@/lib/types";

const META: Record<Status, { Icon: typeof CheckCircle2; cls: string; label: string; bar: string }> = {
  NORMAL: { Icon: CheckCircle2, cls: "text-emerald-300 border-emerald-500/40 bg-emerald-500/10", label: "Normal", bar: "bg-emerald-400" },
  WARNING: { Icon: AlertTriangle, cls: "text-amber-300 border-amber-500/40 bg-amber-500/10", label: "Warning", bar: "bg-amber-400" },
  CRITICAL: { Icon: AlertOctagon, cls: "text-red-300 border-red-500/40 bg-red-500/10", label: "Critical", bar: "bg-red-400" },
};
export const statusBar = (s: Status) => (META[s] ?? META.NORMAL).bar;

export function Stat({ status }: { status: Status }) {
  const m = META[status] ?? META.NORMAL;
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium ${m.cls}`}>
      <m.Icon className="size-3.5" aria-hidden="true" />
      {m.label}
    </span>
  );
}

export function Nav() {
  return (
    <nav className="flex gap-4 text-sm text-zinc-400">
      <Link href="/" className="hover:text-zinc-100">Live Ops</Link>
      <Link href="/scorecard" className="hover:text-zinc-100">Scorecard</Link>
    </nav>
  );
}

export function Waiting({ error }: { error?: string | null }) {
  return (
    <div className="rounded border border-dashed border-zinc-700 p-6 text-center font-mono text-sm text-zinc-400">
      waiting for backend{error ? ` (${error})` : ""}…
    </div>
  );
}

export function Panel({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 ${className}`}>
      <h2 className="mb-3 font-mono text-xs uppercase tracking-widest text-zinc-500">{title}</h2>
      {children}
    </section>
  );
}

export function ApprovalRow({ a, onDone }: { a: { id: string; action: string; expires_in_s?: number; params?: Record<string, unknown> }; onDone?: () => void }) {
  const [msg, setMsg] = useState<string | null>(null);
  async function act(kind: "approve" | "reject") {
    const r = await post(`/actions/${a.id}/${kind}`);
    setMsg(r.status === 409 ? `already ${kind}d` : r.ok ? `${kind}d` : `failed (${r.status})`);
    onDone?.();
  }
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded border border-zinc-800 p-2 text-sm">
      <div>
        <div className="font-mono">{a.action}</div>
        <div className="text-xs text-zinc-500">
          {a.params ? JSON.stringify(a.params) : ""} {a.expires_in_s != null ? `· expires ${a.expires_in_s}s` : ""}
        </div>
      </div>
      {msg ? (
        <span className="font-mono text-xs text-zinc-300">{msg}</span>
      ) : (
        <div className="flex gap-2">
          <Button size="sm" onClick={() => act("approve")}>Approve</Button>
          <Button size="sm" variant="outline" onClick={() => act("reject")}>Reject</Button>
        </div>
      )}
    </li>
  );
}
