"use client";

import { useSyncExternalStore } from "react";
import { clockText } from "@/lib/format";

// One shared 1 Hz ticker. The server snapshot is null, so nothing time-dependent is prerendered.
let now = 0;
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setInterval> | null = null;

function subscribe(cb: () => void) {
  listeners.add(cb);
  if (!timer) {
    now = Date.now();
    timer = setInterval(() => {
      now = Date.now();
      listeners.forEach((l) => l());
    }, 1000);
  }
  return () => {
    listeners.delete(cb);
    if (listeners.size === 0 && timer) {
      clearInterval(timer);
      timer = null;
    }
  };
}

export function useNow(): number | null {
  return useSyncExternalStore(
    subscribe,
    () => now || Date.now(),
    () => null,
  );
}

/** Live countdown to an ISO instant. `data-seconds` exposes the remaining seconds for tests. */
export function Countdown({ to, size = "md", testid = "eta-countdown" }: { to: string | null; size?: "sm" | "md" | "lg"; testid?: string }) {
  const t = useNow();
  const target = to ? Date.parse(to) : NaN;
  const remaining = t === null || Number.isNaN(target) ? null : Math.max(0, Math.round((target - t) / 1000));
  const text = remaining === null ? (to ? "--:--" : "no ETA") : remaining === 0 ? "breach due" : clockText(remaining);
  const sz = { sm: "text-sm", md: "text-lg", lg: "text-3xl sm:text-4xl" }[size];
  return (
    <span
      data-testid={testid}
      data-seconds={remaining ?? ""}
      className={`tabular font-mono font-semibold tracking-tight ${sz}`}
      aria-label={remaining === null ? "ETA unknown" : `${Math.floor(remaining / 60)} minutes ${remaining % 60} seconds to forecast breach`}
    >
      {text}
    </span>
  );
}
