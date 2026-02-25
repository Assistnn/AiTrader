"use client";

import { useState } from "react";
import { Header } from "@/components/common/Header";
import { TraderList } from "@/components/trader/TraderList";
import { BasicInfoTab } from "@/components/trader/tabs/BasicInfoTab";
import { M1M2Tab } from "@/components/trader/tabs/M1M2Tab";
import { M3M4Tab } from "@/components/trader/tabs/M3M4Tab";
import { MXTab } from "@/components/trader/tabs/MXTab";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { useTraders } from "@/hooks/useDashboard";
import type { Trader } from "@/types/api";
import { apiClient } from "@/lib/api";

const defaultStageConfig = {
  enabled: true,
  mode: "rule",
  timeframe: "M15",
  params: {},
};

const defaultMX = {
  evaluationMode: "all",
  scoreWeights: { direction: 0.4, setup: 0.4, execution: 0.2 },
  scoreThreshold: 0.7,
};

export function TraderSettingsPage() {
  const { data: traders, mutate } = useTraders();
  const [selected, setSelected] = useState<Trader | null>(null);
  const [draft, setDraft] = useState<Partial<Trader>>({});
  const [stages, setStages] = useState({
    m1: { ...defaultStageConfig },
    m2: { ...defaultStageConfig },
    m3: { ...defaultStageConfig },
    m4: { ...defaultStageConfig },
  });
  const [mx, setMX] = useState({ ...defaultMX });
  const [saving, setSaving] = useState(false);

  const handleSelect = (trader: Trader) => {
    setSelected(trader);
    setDraft({});
  };

  const handleFieldChange = (field: string, value: unknown) => {
    setDraft((prev) => ({ ...prev, [field]: value }));
  };

  const handleStageChange = (
    stage: "m1" | "m2" | "m3" | "m4",
    field: string,
    value: unknown
  ) => {
    setStages((prev) => {
      const current = prev[stage];
      if (field.startsWith("params.")) {
        const paramKey = field.slice(7);
        return {
          ...prev,
          [stage]: {
            ...current,
            params: { ...current.params, [paramKey]: value },
          },
        };
      }
      return { ...prev, [stage]: { ...current, [field]: value } };
    });
  };

  const handleMXChange = (field: string, value: unknown) => {
    setMX((prev) => {
      if (field.startsWith("scoreWeights.")) {
        const key = field.slice(13);
        return {
          ...prev,
          scoreWeights: { ...prev.scoreWeights, [key]: value },
        };
      }
      return { ...prev, [field]: value };
    });
  };

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await apiClient.put(`/api/v1/traders/${selected.id}`, {
        ...draft,
        stages,
        mx,
      });
      await mutate();
    } catch {
      // error handled by apiClient
    } finally {
      setSaving(false);
    }
  };

  const merged = selected ? { ...selected, ...draft } : null;

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <div className="flex flex-1">
        {/* Left pane: trader list */}
        <aside className="w-64 border-r p-4">
          <TraderList
            traders={traders || []}
            activeId={selected?.id ?? null}
            onSelect={handleSelect}
          />
        </aside>

        {/* Right pane: settings tabs */}
        <main className="flex-1 p-4">
          {!merged ? (
            <p className="text-center text-muted-foreground">
              Select a trader to edit settings
            </p>
          ) : (
            <div className="max-w-[900px]">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-semibold">{merged.name}</h2>
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? "Saving..." : "Save"}
                </Button>
              </div>
              <Tabs defaultValue="basic">
                <TabsList>
                  <TabsTrigger value="basic">Basic</TabsTrigger>
                  <TabsTrigger value="m1m2">M1-M2</TabsTrigger>
                  <TabsTrigger value="m3m4">M3-M4</TabsTrigger>
                  <TabsTrigger value="mx">MX</TabsTrigger>
                </TabsList>
                <TabsContent value="basic">
                  <BasicInfoTab trader={merged as Trader} onChange={handleFieldChange} />
                </TabsContent>
                <TabsContent value="m1m2">
                  <M1M2Tab
                    m1={stages.m1}
                    m2={stages.m2}
                    onM1Change={(f, v) => handleStageChange("m1", f, v)}
                    onM2Change={(f, v) => handleStageChange("m2", f, v)}
                  />
                </TabsContent>
                <TabsContent value="m3m4">
                  <M3M4Tab
                    m3={stages.m3}
                    m4={stages.m4}
                    onM3Change={(f, v) => handleStageChange("m3", f, v)}
                    onM4Change={(f, v) => handleStageChange("m4", f, v)}
                  />
                </TabsContent>
                <TabsContent value="mx">
                  <MXTab mx={mx} onChange={handleMXChange} />
                </TabsContent>
              </Tabs>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
