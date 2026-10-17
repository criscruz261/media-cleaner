import { it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { CleanupComparison } from "./CleanupComparison";
import type { Cleanup } from "../types/api";

it("shows every retained file on the left and only planned deletions on the right without selection controls", () => {
  const files = ["original", "retained-copy", "unwanted"].map((id) => ({
    id,
    name: id + ".jpg",
    path: "/photos/" + id + ".jpg",
    size: 10,
    media_type: "image",
  }));
  render(
    <CleanupComparison
      plan={
        {
          items: [
            {
              group_id: "group",
              classification: "EXACT_DUPLICATE",
              file_id: "unwanted",
              source: files[2].path,
              keeper: files[0].path,
              size: 10,
              review_files: files,
            },
          ],
        } as Cleanup
      }
    />,
  );
  const kept = screen.getByRole("region", { name: "Files to keep" });
  const deleted = screen.getByRole("region", { name: "Files to delete" });
  expect(within(kept).getAllByRole("img")).toHaveLength(2);
  expect(within(kept).getByText("original.jpg")).toBeInTheDocument();
  expect(within(kept).getByText("retained-copy.jpg")).toBeInTheDocument();
  expect(within(deleted).getByText("unwanted.jpg")).toBeInTheDocument();
  expect(within(kept).queryByText("unwanted.jpg")).not.toBeInTheDocument();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("clearly shows when an explicit keep-none group will retain no files", () => {
  render(
    <CleanupComparison
      plan={
        {
          items: [
            {
              file_id: "delete",
              source: "/delete.jpg",
              keeper: null,
              size: 10,
            },
          ],
        } as Cleanup
      }
    />,
  );
  expect(
    screen.getByText("No files will be kept in this group."),
  ).toBeInTheDocument();
  expect(
    within(screen.getByRole("region", { name: "Files to delete" })).getByText(
      "delete.jpg",
    ),
  ).toBeInTheDocument();
});
