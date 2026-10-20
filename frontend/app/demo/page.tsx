import { Placeholder } from "@/components/Placeholder";

export const metadata = { title: "Demo control · Sentinel" };

export default function DemoPage() {
  return (
    <Placeholder title="Demo control" phase="Phase 6">
      Replay controls (mode, seed, speed), chaos faults such as bank_c_slow and otp_p1_down, a live success-rate chart, the
      kill switch and the shadow / enforce toggle.
    </Placeholder>
  );
}
