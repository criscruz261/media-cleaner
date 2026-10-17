import { createContext } from "react";

export const ScannerResetContext = createContext<(() => void) | null>(null);
