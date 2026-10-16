import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { prefix } from "../services/api";
import type { Scan } from "../types/api";
export function useScanProgress(scan?: Scan) {
  const client = useQueryClient();
  useEffect(() => {
    if (!scan || !["queued", "running"].includes(scan.status)) return;
    if (typeof EventSource === "undefined") return;
    const source = new EventSource(`${prefix}/scans/${scan.id}/events`);
    source.onmessage = (event) => {
      const state = JSON.parse(event.data) as Scan;
      client.setQueryData(["scan", scan.id], state);
      client.invalidateQueries({ queryKey: ["scans"] });
      client.invalidateQueries({ queryKey: ["scan-matches", scan.id] });
      if (!["queued", "running"].includes(state.status)) {
        source.close();
        client.invalidateQueries();
      }
    };
    source.onerror = () => {
      // EventSource reconnects automatically; polling continues while disconnected.
      client.invalidateQueries({ queryKey: ["scan", scan.id] });
    };
    return () => source.close();
  }, [scan?.id, scan?.status, client]);
}
