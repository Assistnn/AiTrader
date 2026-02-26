import type { Metadata } from "next";
import { ThemeProvider } from "@/components/common/ThemeProvider";
import { AuthGuard } from "@/components/common/AuthGuard";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Trading System",
  description: "FX/暗号通貨 自動取引システム",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja" suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
          <AuthGuard>{children}</AuthGuard>
        </ThemeProvider>
      </body>
    </html>
  );
}
