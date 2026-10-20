<<<<<<< HEAD
import { Suspense } from "react";
import { apiFetch } from "@/lib/upstream";

async function ApiStatus() {
  let status = "unreachable";
  let csvRows: number | null = null;
  try {
    const res = await apiFetch("/health");
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
=======
import { LiveOps } from "@/components/LiveOps";
>>>>>>> phase-02-generator-sim-ui

export default function Home() {
  return <LiveOps />;
}
