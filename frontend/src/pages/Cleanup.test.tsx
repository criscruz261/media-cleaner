import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Cleanup } from "./Cleanup";
import type { Cleanup as Plan } from "../types/api";
const plan: Plan = {
  id: "plan-1",
  status: "planned",
  token: "confirmation-token",
  destination: "quarantine",
  total_bytes: 100,
  created_at: "2026-01-01T00:00:00Z",
  expires_at: "2026-01-01T00:10:00Z",
  items: [
    {
      file_id: "copy",
      source: "/photos/a copy.jpg",
      keeper: "/photos/a.jpg",
      size: 100,
      status: "planned",
      quarantine_path: null,
      error: null,
    },
  ],
};
describe("cleanup confirmation", () => {
  it("shows source and keeper, and never executes before explicit confirmation", async () => {
    const requests: { url: string; body: unknown }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, options?: RequestInit) => {
        requests.push({
          url,
          body: options?.body ? JSON.parse(options.body as string) : null,
        });
        return {
          ok: true,
          json: async () =>
            url.endsWith("/execute")
              ? { ...plan, status: "completed" }
              : { items: [], total: 0 },
        };
      }),
    );
    const completed = vi.fn();
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    render(
      <QueryClientProvider client={client}>
        <Cleanup plan={plan} onComplete={completed} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("/photos/a copy.jpg")).toBeInTheDocument();
    expect(screen.getByText("Keep: /photos/a.jpg")).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Confirm cleanup" });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(
      requests.filter((request) => request.url.endsWith("/execute")),
    ).toHaveLength(0);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(button).toBeEnabled();
    fireEvent.click(button);
    await waitFor(() => expect(completed).toHaveBeenCalledOnce());
    expect(
      requests.find((request) => request.url.endsWith("/execute"))?.body,
    ).toEqual({
      plan_id: "plan-1",
      token: "confirmation-token",
      confirmed: true,
    });
    vi.unstubAllGlobals();
  });
});
