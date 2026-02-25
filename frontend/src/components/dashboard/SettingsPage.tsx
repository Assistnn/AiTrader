"use client";

import { useState } from "react";
import { Header } from "@/components/common/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type SettingsSection =
  | "exchange"
  | "ai"
  | "safeguard"
  | "cost"
  | "account";

const sections: { key: SettingsSection; label: string }[] = [
  { key: "exchange", label: "Exchange API" },
  { key: "ai", label: "AI API" },
  { key: "safeguard", label: "Safeguard" },
  { key: "cost", label: "Cost Management" },
  { key: "account", label: "Account" },
];

function ExchangeSettings() {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium">GMO Coin API Key</label>
        <Input type="password" placeholder="••••••••" />
      </div>
      <div>
        <label className="text-sm font-medium">GMO Coin Secret Key</label>
        <Input type="password" placeholder="••••••••" />
      </div>
      <Button>Save</Button>
    </div>
  );
}

function AISettings() {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium">OpenAI API Key</label>
        <Input type="password" placeholder="sk-..." />
      </div>
      <div>
        <label className="text-sm font-medium">Google Gemini API Key</label>
        <Input type="password" placeholder="••••••••" />
      </div>
      <div>
        <label className="text-sm font-medium">Anthropic API Key</label>
        <Input type="password" placeholder="sk-ant-..." />
      </div>
      <Button>Save</Button>
    </div>
  );
}

function SafeguardSettings() {
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        Safeguard rules (SG-001 ~ SG-040) are configured at the system level.
        Individual trader overrides can be set in Trader Settings.
      </p>
      <p className="text-sm text-muted-foreground">
        (Detailed safeguard configuration UI will be available in Phase 4)
      </p>
    </div>
  );
}

function CostSettings() {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium">
          Daily Token Budget
        </label>
        <Input type="number" defaultValue={1000000} />
        <p className="mt-0.5 text-xs text-muted-foreground">
          AI calls stop when daily token usage exceeds this limit
        </p>
      </div>
      <div>
        <label className="text-sm font-medium">
          Rate Limit (per trader, per minute)
        </label>
        <Input type="number" defaultValue={10} />
      </div>
      <div>
        <label className="text-sm font-medium">
          Global Rate Limit (per minute)
        </label>
        <Input type="number" defaultValue={30} />
      </div>
      <div>
        <label className="text-sm font-medium">Warning Threshold (%)</label>
        <Input type="number" defaultValue={80} />
      </div>
      <Button>Save</Button>
    </div>
  );
}

function AccountSettings() {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium">Email</label>
        <Input type="email" />
      </div>
      <div>
        <label className="text-sm font-medium">Password</label>
        <Input type="password" />
      </div>
      <Button>Update</Button>
    </div>
  );
}

const sectionComponents: Record<SettingsSection, () => JSX.Element> = {
  exchange: ExchangeSettings,
  ai: AISettings,
  safeguard: SafeguardSettings,
  cost: CostSettings,
  account: AccountSettings,
};

export function SettingsPage() {
  const [active, setActive] = useState<SettingsSection>("exchange");
  const SectionComponent = sectionComponents[active];

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <div className="flex flex-1">
        {/* Left menu */}
        <aside className="w-56 border-r p-4">
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">
            Settings
          </h3>
          <div className="space-y-1">
            {sections.map((s) => (
              <button
                key={s.key}
                onClick={() => setActive(s.key)}
                className={cn(
                  "w-full rounded-md px-3 py-2 text-left text-sm transition-colors",
                  active === s.key
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-accent/50"
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
        </aside>

        {/* Right content */}
        <main className="flex-1 p-6">
          <Card className="max-w-lg">
            <CardHeader>
              <CardTitle className="text-base">
                {sections.find((s) => s.key === active)?.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <SectionComponent />
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  );
}
