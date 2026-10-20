import { StatusBadge } from "@/components/status-badge";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Sentinel</h1>
      <StatusBadge label="OK" />
    </main>
  );
}
