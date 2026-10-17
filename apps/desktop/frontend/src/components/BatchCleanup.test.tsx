import { it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BatchCleanup } from "./BatchCleanup";

it.each(["", "EXACT_DUPLICATE", "SIMILAR_CONTENT"] as const)(
  "previews selections in scope %s without executing cleanup",
  async (classification) => {
    const fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({ id: "combined-plan" }),
    }));
    vi.stubGlobal("fetch", fetch);
    try {
      const onPlan = vi.fn();
      render(
        <QueryClientProvider client={new QueryClient()}>
          <BatchCleanup
            scanId="scan"
            onPlan={onPlan}
            classification={classification}
          />
        </QueryClientProvider>,
      );
      fireEvent.change(screen.getByLabelText("Batch cleanup destination"), {
        target: { value: "quarantine" },
      });
      fireEvent.click(
        screen.getByRole("button", {
          name:
            classification === "EXACT_DUPLICATE"
              ? "Review exact duplicate groups"
              : classification === "SIMILAR_CONTENT"
                ? "Review similar media groups"
                : "Review selected groups",
        }),
      );
      await waitFor(() =>
        expect(onPlan).toHaveBeenCalledWith({ id: "combined-plan" }),
      );
      expect(fetch).toHaveBeenCalledTimes(1);
      const [url, options] = fetch.mock.calls[0] as unknown as [
        string,
        RequestInit,
      ];
      expect(url).toContain("/cleanup/plan-selected");
      expect(JSON.parse(options.body as string)).toEqual({
        scan_id: "scan",
        destination: "quarantine",
        ...(classification ? { classification } : {}),
      });
    } finally {
      vi.unstubAllGlobals();
    }
  },
);

it("finds a banner that loads later and toggles review when scrolling", async () => {
  const view = render(
    <QueryClientProvider client={new QueryClient()}>
      <BatchCleanup scanId="scan" onPlan={vi.fn()} />
    </QueryClientProvider>,
  );
  const button = screen.getByRole("button", { name: "Review selected groups" });
  let top = 300;
  vi.spyOn(button, "getBoundingClientRect").mockImplementation(
    () => ({ top, bottom: top + 32 }) as DOMRect,
  );
  const banner = document.createElement("div");
  banner.className = "sticky-review-progress";
  banner.innerHTML = '<div id="sticky-review-action"></div>';
  vi.spyOn(banner, "getBoundingClientRect").mockReturnValue({
    bottom: 100,
  } as DOMRect);
  document.body.appendChild(banner);
  try {
    top = 20;
    fireEvent.scroll(window);
    await waitFor(() =>
      expect(banner.querySelector("button")).toHaveTextContent(
        "Review selected groups",
      ),
    );
    top = 300;
    fireEvent.scroll(window);
    await waitFor(() => expect(banner.querySelector("button")).toBeNull());
  } finally {
    view.unmount();
    banner.remove();
  }
});
