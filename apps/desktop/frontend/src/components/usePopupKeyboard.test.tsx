import { fireEvent, render } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { usePopupKeyboard } from "./usePopupKeyboard";

function Popup({ close }: { close: () => void }) {
  usePopupKeyboard(true, (event) => {
    if (event.key === "Escape") close();
  });
  return null;
}

it("closes only the top popup regardless of keyboard focus", () => {
  const first = vi.fn(),
    second = vi.fn();
  const view = render(
    <>
      <Popup close={first} />
      <Popup close={second} />
    </>,
  );
  fireEvent.keyDown(document.body, { key: "Escape" });
  expect(second).toHaveBeenCalledOnce();
  expect(first).not.toHaveBeenCalled();
  view.rerender(<Popup close={first} />);
  fireEvent.keyDown(document.body, { key: "Escape" });
  expect(first).toHaveBeenCalledOnce();
  view.unmount();
  fireEvent.keyDown(document.body, { key: "Escape" });
  expect(first).toHaveBeenCalledOnce();
});
