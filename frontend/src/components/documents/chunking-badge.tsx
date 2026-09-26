import { Badge } from "@/components/ui/badge";
import type { ChunkingInfo } from "@/lib/api/types";

/** "auto → markdown" (what was asked → what ran), or "Not recorded" for older documents. */
export function ChunkingBadge({ chunking }: { chunking: ChunkingInfo | null }) {
  if (!chunking?.strategy) {
    return <Badge variant="outline">Not recorded</Badge>;
  }
  const label =
    chunking.requested && chunking.requested !== chunking.strategy
      ? `${chunking.requested} → ${chunking.strategy}`
      : chunking.strategy;
  return <Badge variant="secondary">{label}</Badge>;
}
