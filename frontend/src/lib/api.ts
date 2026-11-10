const TOKEN_KEY = "spendsense.session.v1";
export const session = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export function normalizeApiBase(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, "");
  if (trimmed === "/api") return trimmed;
  return trimmed.replace(/\/api$/, "") || "/";
}

const configuredBase =
  import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || "/api";
export const apiBaseUrl = normalizeApiBase(configuredBase);

function errorMessage(status: number, body: unknown): string {
  const detail =
    body && typeof body === "object" && "detail" in body ? body.detail : null;
  if (status === 422 && Array.isArray(detail)) {
    const fields = [
      ...new Set(
        detail.flatMap((item) =>
          typeof item === "object" && item && Array.isArray(item.loc)
            ? item.loc
                .slice(1)
                .filter((value: unknown) => typeof value === "string")
            : [],
        ),
      ),
    ];
    return fields.length
      ? `Please check ${fields.join(", ").replaceAll("_", " ")} and try again.`
      : "Please check your entries and try again.";
  }
  const known: Record<number, string> = {
    400: "This request could not be completed. Check your entries. Your username or email may already be registered.",
    401: "Please sign in again. Your session may have expired or your credentials are incorrect.",
    403: "You do not have permission to perform this action.",
    404: "This record or feature is unavailable on the connected server.",
    409: "A budget already exists for this category and month. Edit the existing budget instead.",
    422: "Please check your entries. The server could not accept them.",
    429: "Too many requests. Please wait a moment and try again.",
    502: "The AI service could not interpret this request. Please try again.",
    503: "This feature is temporarily unavailable. Please try again later.",
    504: "The AI service took too long. Please try again.",
  };
  return (
    known[status] || "Something went wrong on the server. Please try again."
  );
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = session.get();
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 25000);
  try {
    const response = await fetch(`${apiBaseUrl}/${path.replace(/^\/+/, "")}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      if (response.status === 401 && token && session.get() === token) {
        session.clear();
        window.dispatchEvent(new Event("spendsense:unauthorized"));
      }
      throw new ApiError(response.status, errorMessage(response.status, body));
    }
    return response.status === 204
      ? (undefined as T)
      : ((await response.json()) as T);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      0,
      controller.signal.aborted
        ? "The request timed out. Please try again."
        : "Unable to connect. Check your connection and try again.",
    );
  } finally {
    window.clearTimeout(timeout);
  }
}
export const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});
export async function allPages<T>(path: string): Promise<T[]> {
  const result: T[] = [];
  for (let skip = 0; ; skip += 100) {
    const page = await request<T[]>(`${path}?skip=${skip}&limit=100`);
    result.push(...page);
    if (page.length < 100) return result;
  }
}
