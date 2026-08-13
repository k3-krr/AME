const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler) {
  unauthorizedHandler = handler;
}

export class ApiError extends Error {
  errorCode: string;
  details?: unknown;
  status: number;

  constructor(message: string, errorCode: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.errorCode = errorCode;
    this.status = status;
    this.details = details;
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${path.startsWith("/") ? "" : "/"}${path}`;
  
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "include", // Essential for cross-origin HttpOnly cookies
  });

  if (response.status === 401) {
    if (unauthorizedHandler) {
      unauthorizedHandler();
    }
  }

  if (response.status === 204) {
    return {} as T;
  }

  let data: { message?: string; error_code?: string; details?: unknown } & Record<string, unknown> = {};
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    data = (await response.json()) as typeof data;
  } else {
    const text = await response.text();
    data = { message: text || `HTTP ${response.status} Error` };
  }

  if (!response.ok) {
    // Standard backend validation formats or generic error
    throw new ApiError(
      data.message || "An unexpected error occurred",
      data.error_code || "UNKNOWN_ERROR",
      response.status,
      data.details
    );
  }

  return data as unknown as T;
}
