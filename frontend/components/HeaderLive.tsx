"use client";

import Link from "next/link";
import { Suspense } from "react";
import { usePathname } from "next/navigation";
import { useStream } from "@/lib/stream";
import { Chip, Icon } from "./ui";

const NAV = [
  { href: "/", label: "Live Ops" },
  { href: "/scorecard", label: "Scorecard" },
  { href: "/demo", label: "Demo" },
] as const;

// usePathname is runtime data: the static shell renders the bar with no active tab, then it streams in.
export function NavLinks() {
  return (
    <Suspense fallback={<NavBar path={null} />}>
      <ActiveNav />
    </Suspense>
  );
}

function ActiveNav() {
  return <NavBar path={usePathname()} />;
}

function NavBar({ path }: { path: string | null }) {
  return (
    <nav aria-label="Main" className="-mb-px flex gap-1 overflow-x-auto">
      {NAV.map((n) => {
        const active = path !== null && (n.href === "/" ? path === "/" || path.startsWith("/incidents") : path.startsWith(n.href));
        return (
          <Link
            key={n.href}
            href={n.href}
            data-testid={`nav-${n.label.toLowerCase().replace(/\s+/g, "-")}`}
            aria-current={active ? "page" : undefined}
            className={`border-b-2 px-2.5 py-2 text-[13px] font-medium whitespace-nowrap transition-colors ${
              active ? "border-accent text-foreground" : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {n.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function StreamChip() {
  const { connection, synced } = useStream();
  const live = connection === "open" && synced;
  return (
    <span data-testid="stream-status" data-state={live ? "live" : connection} className="inline-flex items-center gap-1.5 text-xs font-medium text-muted">
      <span className={`size-2 rounded-full ${live ? "live-dot bg-good" : "bg-warn"}`} aria-hidden />
      {live ? "Live" : connection === "reconnecting" ? "Reconnecting…" : "Connecting…"}
    </span>
  );
}

export function AutonomyChip() {
  const { kpis } = useStream();
  const mode = kpis?.autonomy_mode ?? "—";
  const tone = mode === "enforce" ? "warn" : mode === "shadow" ? "accent" : "info";
  return (
    <Chip tone={tone} icon={Icon.shield()} testid="autonomy-chip">
      Autonomy: <span className="uppercase">{mode}</span>
    </Chip>
  );
}
