import { createContext, useContext, useState } from "react";
export type CleanupDestination = "trash" | "quarantine";
export const CleanupDestinationContext = createContext<
  [CleanupDestination, (value: CleanupDestination) => void] | null
>(null);
export function useCleanupDestination() {
  const shared = useContext(CleanupDestinationContext);
  const local = useState<CleanupDestination>("trash");
  return shared ?? local;
}
