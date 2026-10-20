"use client";

import Link from "next/link";
import type { ActionView } from "@/lib/types";
import { actionTitle } from "@/lib/format";
import { Countdown } from "./Countdown";
import { Chip, Icon } from "./ui";

const MODE_TONE = { AUTO: "good", HITL: "warn", DENY: "crit", SHADOW: "accent" } as const;
const MODE_ICON = { AUTO: Icon.bolt, HITL: Icon.shield, DENY: Icon.crit, SHADOW: Icon.info } as const;

/**
 * One proposed/executed action. Approve/Reject call the same-origin proxy, which attaches the operator token
 * server-side; the resulting status change arrives over SSE.
 */
async function decide(id: string, verb: "approve" | "reject") {
  await fetch(`/api/actions/${encodeURIComponent(id)}/${verb}`, { method: "POST" });
}
export function ActionCard({ action: a, compact = false }: { action: ActionView; compact?: boolean }) {
  const pending = a.mode === "HITL" && a.status === "pending";
  const mode = (a.mode in MODE_TONE ? a.mode : "HITL") as keyof typeof MODE_TONE;
  return (
    <div data-testid={`action-${a.id}`} className="enter rounded-lg border border-line bg-surface-2/60 p-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <Chip tone={MODE_TONE[mode]} icon={MODE_ICON[mode]()}>
          {a.mode}
        </Chip>
        <span className="text-[11px] font-medium text-muted capitalize">{String(a.status).replace(/_/g, " ")}</span>
        {a.expires_at && pending && (
          <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-muted">
            {Icon.clock("size-3")} expires <Countdown to={a.expires_at} size="sm" testid={`action-expiry-${a.id}`} />
          </span>
        )}
      </div>
      <div className="mt-1.5 text-sm font-semibold">{actionTitle(a.type, a.params)}</div>
      <p className={`mt-0.5 text-xs leading-relaxed text-muted ${compact ? "line-clamp-2" : ""}`}>{a.reason}</p>
      {compact && (
        <Link href={`/incidents/${encodeURIComponent(a.incident_id)}`} className="mt-1 inline-block font-mono text-[11px] text-accent-ink hover:underline">
          {a.incident_id} →
        </Link>
      )}
      {pending && (
        <div className="mt-2.5 flex gap-2">
          <button
            type="button"
            data-testid={`approve-${a.id}`}
            onClick={() => decide(a.id, "approve")}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-xs font-semibold text-background hover:opacity-90"
          >
            {Icon.check()} Approve
          </button>
          <button
            type="button"
            data-testid={`reject-${a.id}`}
            onClick={() => decide(a.id, "reject")}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md border border-line-strong bg-surface px-3 py-1.5 text-xs font-semibold hover:bg-surface-2"
          >
            {Icon.x()} Reject
          </button>
        </div>
      )}
    </div>
  );
}
