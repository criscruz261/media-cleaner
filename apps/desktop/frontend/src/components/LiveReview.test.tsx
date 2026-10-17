import { useState } from "react";
import { it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GroupPreview, PreviewContext } from "./GroupPreview";
import { GroupCard } from "../pages/Review";
import type { Group } from "../types/api";

it("keeps the preview and scan progress when its group leaves the result page", async () => {
  const group = {
    id: "group",
    scan_id: "scan",
    member_count: 2,
    classification: "EXACT_DUPLICATE",
    evidence: {},
    recoverable: 5,
  } as Group;
  let keep = true;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/review")) keep = false;
      return {
        ok: true,
        json: async () =>
          url.endsWith("/settings")
            ? { cleanup_destination: "trash" }
            : url.endsWith("/scans/scan")
              ? {
                  status: "running",
                  stage: "hashing",
                  processed: 2,
                  discovered: 5,
                }
              : url.endsWith("/review")
                ? { saved: true }
                : {
                    ...group,
                    files: ["one", "two"].map((id) => ({
                      id,
                      name: id + ".jpg",
                      media_type: "image",
                      status: "ready",
                      keep,
                      size: 5,
                      warnings: [],
                      metadata: {},
                    })),
                  },
      };
    }),
  );
  function Harness() {
    const [shown, setShown] = useState(true);
    const [preview, setPreview] = useState<{
      groupId: string;
      initialId: string;
      scanId: string;
    } | null>(null);
    return (
      <PreviewContext.Provider
        value={(groupId, initialId, scanId) =>
          setPreview({ groupId, initialId, scanId })
        }
      >
        <button onClick={() => setShown(false)}>Publish next page</button>
        {shown && <GroupCard group={group} onPlan={vi.fn()} />}
        {preview && (
          <GroupPreview {...preview} onClose={() => setPreview(null)} />
        )}
      </PreviewContext.Provider>
    );
  }
  try {
    render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <Harness />
      </QueryClientProvider>,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Enlarge one.jpg" }),
    );
    await screen.findByRole("dialog", { name: "Group preview" });
    await screen.findByText(/Scanning continues/);
    fireEvent.click(screen.getByRole("button", { name: "Publish next page" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("one.jpg")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Select for deletion" }),
    );
    await waitFor(() => expect(screen.getByRole("checkbox")).toBeChecked());
    expect(screen.getByText(/2 \/ 5 files processed/)).toBeInTheDocument();
  } finally {
    vi.unstubAllGlobals();
  }
});
