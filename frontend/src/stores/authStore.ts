/**
 * Auth store: JWT token management.
 * - accessToken: localStorage (short-lived, 1h)
 * - refreshToken: HttpOnly Cookie (server-managed, not accessible from JS)
 * Reference: 08_API仕様, 11_セキュリティ §2-1
 */

import { create } from "zustand";

interface AuthState {
  accessToken: string | null;
  isAuthenticated: boolean;
  setTokens: (accessToken: string) => void;
  clearTokens: () => void;
  loadFromStorage: () => void;
}

const STORAGE_KEY_ACCESS = "ai_trading_access_token";

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  isAuthenticated: false,

  setTokens: (accessToken) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_ACCESS, accessToken);
    }
    set({ accessToken, isAuthenticated: true });
  },

  clearTokens: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_KEY_ACCESS);
      // Legacy cleanup: remove refresh token if still present from old version
      localStorage.removeItem("ai_trading_refresh_token");
    }
    set({ accessToken: null, isAuthenticated: false });
  },

  loadFromStorage: () => {
    if (typeof window === "undefined") return;
    const accessToken = localStorage.getItem(STORAGE_KEY_ACCESS);
    if (accessToken) {
      set({ accessToken, isAuthenticated: true });
    }
  },
}));
