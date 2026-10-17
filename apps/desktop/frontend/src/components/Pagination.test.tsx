import { it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Pagination } from "./ui";

it("jumps to the final partial page and any chosen page with the current group page size", () => {
  const change = vi.fn(),
    resize = vi.fn();
  const view = render(
    <Pagination
      offset={0}
      total={157}
      size={20}
      onChange={change}
      onSizeChange={resize}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Last" }));
  expect(change).toHaveBeenLastCalledWith(140);
  view.rerender(
    <Pagination
      offset={140}
      total={157}
      size={20}
      onChange={change}
      onSizeChange={resize}
    />,
  );
  expect(screen.getByText("141–157 of 157")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Last" })).toBeDisabled();
  const page = screen.getByRole("spinbutton", { name: "Page number" });
  expect(page).toHaveAttribute("max", "8");
  fireEvent.change(page, { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "Go" }));
  expect(change).toHaveBeenLastCalledWith(40);
  fireEvent.change(screen.getByLabelText("Groups per page"), {
    target: { value: "50" },
  });
  expect(resize).toHaveBeenCalledWith(50);
});

it("keeps the group size selector available for a single or empty page", () => {
  render(
    <Pagination
      offset={0}
      total={0}
      size={10}
      onChange={vi.fn()}
      onSizeChange={vi.fn()}
    />,
  );
  expect(screen.getByLabelText("Groups per page")).toBeInTheDocument();
  expect(screen.getByText("0–0 of 0")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
});

it("offers 100 and the full group count as page sizes", () => {
  const resize = vi.fn();
  render(
    <Pagination
      offset={0}
      total={749}
      size={10}
      onChange={vi.fn()}
      onSizeChange={resize}
    />,
  );
  const select = screen.getByLabelText("Groups per page");
  expect(
    [...select.querySelectorAll("option")].map((option) => option.value),
  ).toEqual(["5", "10", "20", "50", "100", "749"]);
  fireEvent.change(select, { target: { value: "749" } });
  expect(resize).toHaveBeenCalledWith(749);
});
