import { api } from "./api";
import type { Group, Page } from "../types/api";

// Keep server requests bounded while allowing the UI to show the full result set.
export async function groupPage<T extends Page<Group>>(
  path: string,
  offset: number,
  size: number,
): Promise<T> {
  const first = await api<T>(
    `${path}&offset=${offset}&limit=${Math.min(size, 50)}`,
  );
  const items = [...first.items];
  const target = Math.min(size, Math.max(0, first.total - offset));
  while (items.length < target) {
    const next = await api<T>(
      `${path}&offset=${offset + items.length}&limit=${Math.min(50, target - items.length)}`,
    );
    if (!next.items.length) break;
    items.push(...next.items);
  }
  return { ...first, items };
}
