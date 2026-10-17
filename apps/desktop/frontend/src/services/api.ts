export const prefix = "/api/v1";
export async function api<T>(
  path: string,
  body?: unknown,
  method?: string,
): Promise<T> {
  const response = await fetch(prefix + path, {
    method: method ?? (body === undefined ? "GET" : "POST"),
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.error?.message ?? `Request failed (${response.status})`,
    );
  return data as T;
}
export function bytes(value: number): string {
  if (!value) return "0 B";
  const exponent = Math.min(Math.floor(Math.log(value) / Math.log(1024)), 4);
  return `${(value / 1024 ** exponent).toFixed(exponent ? 1 : 0)} ${["B", "KB", "MB", "GB", "TB"][exponent]}`;
}

export function displayLabel(value: string | null | undefined): string {
  const text = (value ?? "").replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
