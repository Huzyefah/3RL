import { Placeholder } from "@/components/Placeholder";

export const metadata = { title: "Scorecard · Sentinel" };

export default function ScorecardPage() {
  return (
    <Placeholder title="Scorecard" phase="Phase 6">
      The ablation table B0 → S3 with bootstrap CIs on held-out data, lead-time distribution, Skeptic on/off, RCA quality,
      PKR protected (estimate), cost per incident, and the raw PS-02 CSV panel. Every number comes from scorecard.json.
    </Placeholder>
  );
}
