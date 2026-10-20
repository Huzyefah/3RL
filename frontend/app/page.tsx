import { Suspense } from "react";
import { apiFetch } from "@/lib/upstream";

async function ApiStatus() {
  let status = "unreachable";
  let csvRows: number | null = null;
  try {
    const res = await apiFetch("/healthz");
    const body = await res.json();
    status = body.status;
    csvRows = body.csv_rows;
  } catch {}
  const ok = status === "ok";
  return (
    <p data-testid="api-status" className="text-lg">
      <span aria-hidden>{ok ? "✅" : "⛔"}</span> sentinel-api: <strong>{ok ? "OK" : "Unreachable"}</strong>
      {csvRows !== null && <> · PS-02 rows loaded: <strong data-testid="csv-rows">{csvRows}</strong></>}
    </p>
  );
}

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">Sentinel · NovaPay</h1>
      <p className="text-zinc-600 dark:text-zinc-400">
        Agentic AIOps for PS-02. Predicts payment incidents, argues false alarms down, acts under policy.
      </p>
      <Suspense fallback={<p>Checking API…</p>}>
        <ApiStatus />
      </Suspense>
    </main>
  );
}
