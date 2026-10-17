import { it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScanWorkflow } from "./ScanWorkflow";
import type { Scan } from "../types/api";

it.each([
  ["running", "discovery", "Discover files", "Discovering media"],
  ["running", "metadata_and_hashing", "Analyze & match", "Analyzing media"],
  ["running", "grouping", "Finalize groups", "Finalizing match groups"],
  ["completed", "completed", "Review & clean up", "Scan complete"],
  ["paused", "Checkpoint saved", "Analyze & match", "Paused"],
])(
  "shows the real workflow stage for %s / %s",
  (status, stage, label, description) => {
    render(
      <ScanWorkflow
        scan={{ status, stage, discovered: 10, processed: 5 } as Scan}
      />,
    );
    expect(screen.getByText(label).closest("li")).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(screen.getByText(new RegExp(description))).toBeInTheDocument();
    if (status === "paused") {
      expect(screen.getByText("Stopped")).toBeInTheDocument();
      expect(screen.queryByText("In progress")).not.toBeInTheDocument();
      expect(screen.getByText(/Resume the saved scan/)).toBeInTheDocument();
    }
  },
);
