import { useEffect, useRef } from "react";

const popups: symbol[] = [];

// Capture keys even when disabling a focused control returns focus to the body.
export function usePopupKeyboard(
  enabled: boolean,
  handleKey: (event: KeyboardEvent) => void,
) {
  const handler = useRef(handleKey);
  handler.current = handleKey;
  useEffect(() => {
    if (!enabled) return;
    const id = Symbol("popup");
    popups.push(id);
    const listener = (event: KeyboardEvent) => {
      if (popups.at(-1) !== id) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
      handler.current(event);
    };
    window.addEventListener("keydown", listener, true);
    return () => {
      popups.splice(popups.indexOf(id), 1);
      window.removeEventListener("keydown", listener, true);
    };
  }, [enabled]);
}
