import { Suspense } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/upstream";
import { AutonomyChip, NavLinks, StreamChip } from "./HeaderLive";
import { Chip, Icon } from "./ui";

async function ApiStatus() {
  let ok = false;
  let csvRows: number | null = null;
  try {
    const res = await apiFetch("/health");
    const body = await res.json();
    ok = body.status === "ok";
    csvRows = typeof body.csv_rows === "number" ? body.csv_rows : null;
  } catch {}
  return (
    <Chip tone={ok ? "good" : "crit"} icon={ok ? Icon.ok() : Icon.crit()} testid="api-status">
      API {ok ? "OK" : "Unreachable"}
      {csvRows !== null && (
        <span className="font-normal opacity-80">
          · <span data-testid="csv-rows">{csvRows}</span> rows
        </span>
      )}
    </Chip>
  );
}

export function AppHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-4 gap-y-2 px-4 pt-2.5 sm:px-6">
        <Link href="/" className="flex items-center gap-2" aria-label="Sentinel · NovaPay home">
          <span className="grid size-7 place-items-center rounded-lg bg-foreground text-background">{Icon.shield("size-4")}</span>
          <span className="text-[15px] font-semibold tracking-tight whitespace-nowrap">
            Sentinel <span className="text-faint">·</span> NovaPay
          </span>
        </Link>
        <span
          data-testid="synthetic-badge"
          title="Data is a synthetic replay of the PS-02 sample; NovaPay and its partner banks are fictional."
          className="rounded border border-dashed border-line-strong px-1.5 py-0.5 text-[10px] font-semibold tracking-wider text-muted uppercase"
        >
          Synthetic replay
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <StreamChip />
          <AutonomyChip />
          <Suspense
            fallback={
              <Chip tone="info" icon={Icon.clock()}>
                Checking API…
              </Chip>
            }
          >
            <ApiStatus />
          </Suspense>
        </div>
        <div className="basis-full">
          <NavLinks />
        </div>
      </div>
    </header>
  );
}
