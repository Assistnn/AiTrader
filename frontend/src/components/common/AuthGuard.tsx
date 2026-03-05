"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import { apiClient } from "@/lib/api";

const PUBLIC_PATHS = ["/login"];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, accessToken } = useAuthStore();

  // Synchronously load tokens during useState initialization to avoid
  // an extra render frame. Also sync apiClient token immediately so
  // child components can make authenticated API calls on first render.
  const [ready] = useState(() => {
    if (typeof window !== "undefined") {
      useAuthStore.getState().loadFromStorage();
      const token = useAuthStore.getState().accessToken;
      if (token) {
        apiClient.setToken(token);
      }
      return true;
    }
    return false;
  });

  // Keep apiClient token in sync when it changes (login/logout)
  useEffect(() => {
    apiClient.setToken(accessToken);
  }, [accessToken]);

  useEffect(() => {
    if (!ready) return;
    const authed = useAuthStore.getState().isAuthenticated;
    const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
    if (!authed && !isPublic) {
      router.replace("/login");
    }
    if (authed && pathname === "/login") {
      router.replace("/");
    }
  }, [ready, isAuthenticated, pathname, router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  if (!useAuthStore.getState().isAuthenticated && !isPublic) {
    return null;
  }

  return <>{children}</>;
}
