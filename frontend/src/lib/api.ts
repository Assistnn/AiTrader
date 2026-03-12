/**
 * API client for backend communication.
 * Reference: 08_API仕様, 10_フロントエンドアーキテクチャ, 11_セキュリティ §2-1
 *
 * - credentials: "include" on all requests (for HttpOnly refresh cookie)
 * - refreshToken is sent via cookie, not request body
 */

import type { ApiResponse } from "@/types/api";
import { useAuthStore } from "@/stores/authStore";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;
  private refreshing: Promise<boolean> | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  setToken(token: string | null) {
    this.token = token;
  }

  getToken(): string | null {
    return this.token;
  }

  private headers(): HeadersInit {
    const h: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.token) {
      h["Authorization"] = `Bearer ${this.token}`;
    }
    return h;
  }

  async get<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "GET",
      headers: this.headers(),
      credentials: "include",
    });
    return this.handleResponse<T>(res, "GET", path);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: this.headers(),
      body: body ? JSON.stringify(body) : undefined,
      credentials: "include",
    });
    return this.handleResponse<T>(res, "POST", path, body);
  }

  async put<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "PUT",
      headers: this.headers(),
      body: JSON.stringify(body),
      credentials: "include",
    });
    return this.handleResponse<T>(res, "PUT", path, body);
  }

  async del<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: this.headers(),
      credentials: "include",
    });
    return this.handleResponse<T>(res, "DELETE", path);
  }

  /**
   * Attempt to refresh the access token using the HttpOnly refresh cookie.
   * Returns true if refresh succeeded, false otherwise.
   * Reference: 11_セキュリティ §2-1 — refreshToken is in HttpOnly cookie
   */
  private async tryRefresh(): Promise<boolean> {
    try {
      const res = await fetch(`${this.baseUrl}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({}),
      });

      if (!res.ok) return false;

      const json = await res.json();
      const newAccessToken =
        json.status === "ok" && json.data
          ? json.data.accessToken
          : json.accessToken;

      if (!newAccessToken) return false;

      this.token = newAccessToken;
      useAuthStore.getState().setTokens(newAccessToken);
      return true;
    } catch {
      return false;
    }
  }

  private async handleResponse<T>(
    res: Response,
    method: string,
    path: string,
    body?: unknown
  ): Promise<T> {
    if (res.status === 401) {
      // Skip refresh for auth endpoints to avoid infinite loop
      if (path.startsWith("/api/v1/auth/")) {
        this.forceLogout();
        throw new Error("Unauthorized");
      }

      // Deduplicate concurrent refresh attempts
      if (!this.refreshing) {
        this.refreshing = this.tryRefresh().finally(() => {
          this.refreshing = null;
        });
      }

      const refreshed = await this.refreshing;
      if (refreshed) {
        // Retry original request with new token
        const retryRes = await fetch(`${this.baseUrl}${path}`, {
          method,
          headers: this.headers(),
          body: body ? JSON.stringify(body) : undefined,
          credentials: "include",
        });
        return this.parseResponse<T>(retryRes);
      }

      this.forceLogout();
      throw new Error("Unauthorized");
    }

    return this.parseResponse<T>(res);
  }

  private async parseResponse<T>(res: Response): Promise<T> {
    const json = await res.json();

    // Support both wrapped { status, data } and direct response formats
    if (json.status === "error") {
      throw new Error(json.error?.message || `HTTP ${res.status}`);
    }

    if (!res.ok) {
      throw new Error(json.detail || json.message || `HTTP ${res.status}`);
    }

    // If response has ApiResponse wrapper, extract data; otherwise return as-is
    if (json.status === "ok" && "data" in json) {
      return json.data as T;
    }

    return json as T;
  }

  private forceLogout() {
    this.token = null;
    useAuthStore.getState().clearTokens();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }
}

export const apiClient = new ApiClient(API_BASE);

/** SWR fetcher using apiClient — unwraps {status, data} automatically. */
export const fetcher = <T>(path: string): Promise<T> => apiClient.get<T>(path);

/**
 * Paginated fetcher — returns {data, pagination} for endpoints with pagination.
 * The backend returns {status: "ok", data: [...], pagination: {...}}.
 */
export const paginatedFetcher = async <T>(path: string): Promise<{data: T[]; pagination: {page: number; perPage: number; totalItems: number; totalPages: number}}> => {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      ...(apiClient.getToken() ? { Authorization: `Bearer ${apiClient.getToken()}` } : {}),
    },
    credentials: "include",
  });

  if (res.status === 401) {
    useAuthStore.getState().clearTokens();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  const json = await res.json();
  if (json.status === "error") throw new Error(json.error?.message || `HTTP ${res.status}`);

  return {
    data: (json.data ?? []) as T[],
    pagination: json.pagination ?? { page: 1, perPage: 20, totalItems: 0, totalPages: 0 },
  };
};
