import type { Band } from "./types";

export const BAND_WARNING = 0.75;
export const BAND_CRITICAL = 0.95;

export function bandOf(u: number): Band {
  if (u >= BAND_CRITICAL) return "CRITICAL";
  if (u >= BAND_WARNING) return "WARNING";
  return "NORMAL";
}

/** PKR in compact form: 1,250,000 → "1.25M". */
export function pkrCompact(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toFixed(0);
}

export const pct = (x: number, digits = 1) => `${(x * 100).toFixed(digits)}%`;

/** mm:ss (or h:mm:ss) for a non-negative number of seconds. */
export function clockText(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

/** Wall-clock time in Pakistan Standard Time (UTC+5, no DST), e.g. "13:54:10". */
export function hhmmss(iso: string): string {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? "" : new Date(t + 5 * 3600_000).toISOString().slice(11, 19);
}

export function segmentLabel(segment: string | null | undefined): string {
  return segment ?? "platform";
}

export const actionTitle = (type: string, params: Record<string, unknown>): string => {
  if (type === "reroute_bank") return `Reroute ${params.bank ?? "bank"} IBFT → ${params.rail ?? "RAAST"}`;
  if (type === "otp_failover") return `Fail over OTP ${params.from ?? "P1"} → ${params.to ?? "P2"}`;
  return type.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
};
