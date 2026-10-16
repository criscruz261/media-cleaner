import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MediaPreview } from "./MediaPreview";
import type { MediaFile } from "../types/api";
const file: MediaFile = {
  id: "clip-id",
  name: "clip.MOV",
  path: "/photos/clip.MOV",
  size: 100,
  sha256: "abc",
  status: "ready",
  media_type: "video",
  keep: true,
  protected_reason: null,
  metadata: {},
  warnings: [],
};
describe("media preview", () => {
  it("plays videos from an authenticated range-capable endpoint without preloading entire media", () => {
    const { container } = render(<MediaPreview file={file} />);
    const video = container.querySelector("video")!;
    expect(video).toHaveAttribute("controls");
    expect(video).toHaveAttribute("poster", "/api/v1/files/clip-id/thumbnail");
    expect(video).toHaveAttribute("preload", "none");
    expect(video).toHaveAttribute("src", "/api/v1/files/clip-id/preview");
    fireEvent.error(video);
    expect(screen.getByText(/Preview unavailable/)).toBeInTheDocument();
  });
});

it("shows an actual video thumbnail in Scanner until the user plays it", () => {
  const { container } = render(<MediaPreview file={file} thumbnailFirst />);
  expect(
    screen.getByRole("img", { name: "Thumbnail of clip.MOV" }),
  ).toHaveAttribute("src", "/api/v1/files/clip-id/thumbnail");
  expect(container.querySelector("video")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Play clip.MOV" }));
  expect(container.querySelector("video")).toHaveAttribute("controls");
  expect(container.querySelector("video")).toHaveAttribute("autoplay");
});
