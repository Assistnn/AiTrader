/**
 * Auth store: JWT token management with localStorage persistence.
 * Reference: 08_API仕様
 */

import { create } from "zustand";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  setTokens: (accessToken: string, refreshToken: string) => void;
  clearTokens: () => void;
  loadFromStorage: () => void;
}

const STORAGE_KEY_ACCESS = "ai_trading_access_token";
const STORAGE_KEY_REFRESH = "ai_trading_refresh_token";

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,

  setTokens: (accessToken, refreshToken) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_ACCESS, accessToken);
      localStorage.setItem(STORAGE_KEY_REFRESH, refreshToken);
    }
    set({ accessToken, refreshToken, isAuthenticated: true });
  },

  clearTokens: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_KEY_ACCESS);
      localStorage.removeItem(STORAGE_KEY_REFRESH);
    }
    set({ accessToken: null, refreshToken: null, isAuthenticated: false });
  },

  loadFromStorage: () => {
    if (typeof window === "undefined") return;
    const accessToken = localStorage.getItem(STORAGE_KEY_ACCESS);
    const refreshToken = localStorage.getItem(STORAGE_KEY_REFRESH);
    if (accessToken && refreshToken) {
      set({ accessToken, refreshToken, isAuthenticated: true });
    }
  },
}));
