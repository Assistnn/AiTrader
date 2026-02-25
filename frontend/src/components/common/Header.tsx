"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAlertStore } from "@/stores/alertStore";

const navItems = [
  { href: "/", label: "Dashboard" },
  { href: "/traders", label: "Traders" },
  { href: "/history", label: "History" },
  { href: "/backtests", label: "Backtest" },
  { href: "/pipeline-logs", label: "Logs" },
  { href: "/config-changes", label: "Changes" },
  { href: "/settings", label: "Settings" },
];

export function Header() {
  const pathname = usePathname();
  const unreadCount = useAlertStore((s) => s.unreadCount);

  return (
    <header className="border-b bg-card">
      <div className="flex h-14 items-center px-4">
        <Link href="/" className="mr-8 text-lg font-bold tracking-tight">
          AI Trading
        </Link>
        <nav className="flex items-center gap-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "rounded-md px-3 py-2 text-sm transition-colors",
                pathname === item.href
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground"
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-4">
          {unreadCount > 0 && (
            <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1.5 text-xs font-medium text-destructive-foreground">
              {unreadCount}
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
