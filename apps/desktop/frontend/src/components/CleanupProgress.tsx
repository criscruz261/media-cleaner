import { useQuery } from "@tanstack/react-query";
import { api, bytes } from "../services/api";

type Progress = {
  status: string;
  total: number;
  processed: number;
  moved: number;
  failed: number;
  moved_bytes: number;
  total_bytes: number;
  current_file: string | null;
  current_action: string | null;
};
export function CleanupProgress({
  planId,
  total,
}: {
  planId: string;
  total: number;
}) {
  const progress = useQuery({
    queryKey: ["cleanup-progress", planId],
    queryFn: () => api<Progress>(`/cleanup/${planId}/progress`),
    refetchInterval: 400,
    retry: false,
  });
  const data = progress.data;
  const validating = !data || data.status === "planned";
  return (
    <section className="panel cleanup-progress" aria-label="Deletion progress">
      <h2>
        {validating
          ? "Validating files before deletion…"
          : "Deleting selected files…"}
      </h2>
      <p role="status">
        {data?.processed ?? 0} / {data?.total ?? total} files processed
      </p>
      <progress
        aria-label="Deletion progress"
        max={Math.max(1, data?.total ?? total)}
        value={validating ? undefined : data.processed}
      />
      {validating ? (
        <p>
          Checking selected files and retained copies before moving anything.
        </p>
      ) : (
        <>
          <p>
            {data.moved} moved · {data.failed} failed ·{" "}
            {bytes(data.moved_bytes)} of {bytes(data.total_bytes)} moved
          </p>
          {data.current_file && (
            <p className="cleanup-current-file">
              {data.current_action === "moving" ? "Moving" : "Checking"}:{" "}
              {data.current_file}
            </p>
          )}
        </>
      )}
      {progress.error && (
        <p role="alert">
          Progress temporarily unavailable. The cleanup request is still
          running.
        </p>
      )}
    </section>
  );
}
