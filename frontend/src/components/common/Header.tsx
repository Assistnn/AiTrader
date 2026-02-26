"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Bot,
  Bell,
  ClipboardList,
  Settings,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "./ThemeToggle";
import { useAlertStore } from "@/stores/alertStore";
import { useAuthStore } from "@/stores/authStore";
import { apiClient } from "@/lib/api";

const navItems = [
  { href: "/", label: "ダッシュボード", icon: LayoutDashboard },
  { href: "/traders", label: "トレーダー設定", icon: Bot },
  { href: "/notifications", label: "通知設定", icon: Bell },
  { href: "/history", label: "取引履歴", icon: ClipboardList },
  { href: "/settings", label: "システム設定", icon: Settings },
];

export function Header() {
  const pathname = usePathname();
  const unreadCount = useAlertStore((s) => s.unreadCount);
  const clearTokens = useAuthStore((s) => s.clearTokens);
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  const handleLogout = async () => {
    try {
      await apiClient.post("/api/v1/auth/logout");
    } catch {
      // Ignore errors — we clear tokens regardless
    }
    clearTokens();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  };

  // Close menu on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    };
    if (showMenu) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showMenu]);

  return (
    <header className="border-b bg-card">
      <div className="flex h-14 items-center px-6">
        {/* Logo */}
        <Link href="/" className="mr-8 text-lg font-bold tracking-tight whitespace-nowrap">
          AI Trading System
        </Link>

        {/* Center Nav */}
        <nav className="flex flex-1 items-center justify-center gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-nav-active text-nav-active-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
                {item.href === "/notifications" && unreadCount > 0 && (
                  <span className="ml-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium text-destructive-foreground">
                    {unreadCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {/* VPS Status */}
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <span className="h-2 w-2 rounded-full bg-profit" />
            <span>VPS稼働中</span>
          </div>

          {/* Theme Toggle */}
          <ThemeToggle />

          {/* User Avatar with dropdown */}
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-xs font-medium hover:ring-2 hover:ring-ring"
            >
              U
            </button>

            {showMenu && (
              <div className="absolute right-0 top-10 z-20 w-40 rounded-lg border bg-popover p-1 shadow-md">
                <button
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-destructive hover:bg-destructive/10"
                >
                  <LogOut className="h-4 w-4" />
                  ログアウト
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
