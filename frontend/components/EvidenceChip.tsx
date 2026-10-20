"use client";

import { useId } from "react";

const KIND: Record<string, string> = {
  segment: "Segment breakdown (per-bank counts, binomial test)",
  forecast: "Holt forecast and ETA to SLO breach",
  log: "Redacted log template with novelty count",
  metric: "Metric window",
  change: "Change / deploy event",
  calendar: "Business or maintenance calendar",
  memory: "Similar past incident (recall_similar)",
  topology: "Service dependency graph",
  impact: "Impact estimate",
  policy: "Policy guard verdict",
  verify: "Post-action verification",
};

/** Clickable evidence id. Opens a native popover (top layer) so it never widens the page on mobile. */
export function EvidenceChip({ id, context }: { id: string; context?: string }) {
  const popId = `ev-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const kind = id.split(":")[0];
  return (
    <>
      <button
        type="button"
        popoverTarget={popId}
        data-testid={`evidence-${id}`}
        className="inline-flex max-w-full items-center gap-1 rounded border border-line-strong bg-surface px-1.5 py-px font-mono text-[11px] text-accent-ink hover:border-accent hover:bg-accent-soft"
        title={`Evidence ${id}`}
      >
        <svg viewBox="0 0 16 16" className="size-3 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
          <path d="M6.6 9.4l2.8-2.8M7 4.4l1.2-1.2a2.8 2.8 0 014 4L11 8.4M9 11.6l-1.2 1.2a2.8 2.8 0 01-4-4L5 7.6" />
        </svg>
        <span className="truncate">{id}</span>
      </button>
      <div id={popId} popover="auto" className="evidence-pop" data-testid="evidence-popover">
        <div className="text-[11px] font-medium tracking-wide text-muted uppercase">Evidence</div>
        <div className="mt-1 font-mono text-sm font-semibold break-all">{id}</div>
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-muted">Kind</dt>
          <dd>{KIND[kind] ?? kind}</dd>
          {context && (
            <>
              <dt className="text-muted">Cited by</dt>
              <dd>{context}</dd>
            </>
          )}
          <dt className="text-muted">Grounding</dt>
          <dd>Resolves to a stored tool output; claims without a resolving id are rejected (I5).</dd>
        </dl>
        <button type="button" popoverTarget={popId} popoverTargetAction="hide" className="mt-4 rounded-md border border-line-strong px-3 py-1 text-xs font-semibold hover:bg-surface-2">
          Close
        </button>
      </div>
    </>
  );
}
