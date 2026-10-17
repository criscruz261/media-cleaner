import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { saveLocal } from "../services/workspace";
const Context = createContext<[number, (value: number) => void] | null>(null);
export function CompactGroupsProvider({ children }: { children: ReactNode }) {
  const [compact, setCompact] = useState(() => {
    try {
      const saved = Number(localStorage.getItem("media-cleaner.compact-level"));
      if ([1, 2, 3, 4, 5].includes(saved)) return saved;
      return localStorage.getItem("media-cleaner.compact-groups") === "true"
        ? 3
        : 1;
    } catch {
      return 1;
    }
  });
  useEffect(() => saveLocal("media-cleaner.compact-level", compact), [compact]);
  return (
    <Context.Provider value={[compact, setCompact]}>
      {children}
    </Context.Provider>
  );
}
export function useCompactGroups() {
  const shared = useContext(Context);
  const local = useState(1);
  return shared ?? local;
}
