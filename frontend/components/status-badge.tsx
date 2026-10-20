import { Badge } from "@/components/ui/badge";

// Status colour is never the only signal: always icon + text.
export function StatusBadge({ label = "OK" }: { label?: string }) {
  return (
    <Badge variant="outline" data-testid="status-badge">
      <span aria-hidden="true">●</span>
      <span>{label}</span>
    </Badge>
  );
}
