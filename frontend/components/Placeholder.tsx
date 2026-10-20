import type { ReactNode } from "react";

export function Placeholder({ title, phase, children }: { title: string; phase: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      <div data-testid="placeholder" className="rounded-xl border border-dashed border-line-strong bg-surface px-5 py-10 text-center">
        <p className="text-sm font-semibold">Arrives in {phase}</p>
        <p className="mx-auto mt-1 max-w-prose text-sm text-muted">{children}</p>
      </div>
    </div>
  );
}
