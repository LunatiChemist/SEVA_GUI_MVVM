import { BoxConnectionDto } from "../../domain/settings";
import { SevaUiError } from "../../domain/errors";

export interface HttpRequestOptions {
  method?: "GET" | "POST";
  path: string;
  body?: unknown;
  timeoutMs?: number;
  headers?: Record<string, string>;
}

export class HttpClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly defaultTimeoutMs: number;

  constructor(box: BoxConnectionDto, defaultTimeoutMs: number) {
    this.baseUrl = box.baseUrl.replace(/\/+$/, "");
    this.apiKey = box.apiKey;
    this.defaultTimeoutMs = defaultTimeoutMs;
  }

  async requestJson<T>(options: HttpRequestOptions): Promise<T> {
    const response = await this.request(options);
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new SevaUiError({
        status: response.status,
        code: "http.invalid_content_type",
        message: `Expected JSON response, got ${contentType || "unknown"}.`
      });
    }
    return (await response.json()) as T;
  }

  async requestBlob(options: HttpRequestOptions): Promise<Blob> {
    const response = await this.request(options);
    return response.blob();
  }

  private async request(options: HttpRequestOptions): Promise<Response> {
    const controller = new AbortController();
    const timeout = options.timeoutMs ?? this.defaultTimeoutMs;
    const handle = setTimeout(() => controller.abort(), timeout);
    const method = options.method ?? "GET";
    const headers = new Headers(options.headers || {});

    if (this.apiKey) {
      headers.set("X-API-Key", this.apiKey);
    }

    let body: BodyInit | undefined;
    if (options.body !== undefined) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(options.body);
    }

    try {
      const response = await fetch(`${this.baseUrl}${options.path}`, {
        method,
        headers,
        body,
        signal: controller.signal
      });
      if (!response.ok) {
        throw await this.buildApiError(response, method, options.path);
      }
      return response;
    } catch (error) {
      if (error instanceof SevaUiError) {
        throw error;
      }
      if (error instanceof Error && error.name === "AbortError") {
        throw new SevaUiError({
          code: "http.timeout",
          message: `Request timed out after ${timeout} ms.`,
          cause: error
        });
      }
      throw new SevaUiError({
        code: "http.network_error",
        message: (error as Error).message || "Network request failed.",
        cause: error
      });
    } finally {
      clearTimeout(handle);
    }
  }

  private async buildApiError(response: Response, method: string, path: string): Promise<SevaUiError> {
    const status = response.status;
    let payload: unknown = undefined;
    let code = "api.request_failed";
    let message = `${method} ${path} failed with status ${status}.`;
    let hint: string | undefined = undefined;

    try {
      payload = await response.json();
      if (payload && typeof payload === "object") {
        const maybe = payload as Record<string, unknown>;
        if (typeof maybe.code === "string" && maybe.code.trim()) {
          code = maybe.code;
        }
        if (typeof maybe.message === "string" && maybe.message.trim()) {
          message = maybe.message;
        }
        if (typeof maybe.hint === "string" && maybe.hint.trim()) {
          hint = maybe.hint;
        }
      }
    } catch {
      // keep generic error text when payload is not JSON
    }

    return new SevaUiError({
      status,
      code,
      message,
      hint,
      cause: payload
    });
  }
}
