"use client";

import { useState } from "react";
import { Header } from "@/components/common/Header";
import { TraderList } from "@/components/trader/TraderList";
import { BasicInfoTab } from "@/components/trader/tabs/BasicInfoTab";
import { M1M2Tab } from "@/components/trader/tabs/M1M2Tab";
import { M3M4Tab } from "@/components/trader/tabs/M3M4Tab";
import { MXTab } from "@/components/trader/tabs/MXTab";
import { SafeguardTab } from "@/components/trader/tabs/SafeguardTab";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Play, Plus, Square, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useTraders } from "@/hooks/useDashboard";
import type { Trader } from "@/types/api";
import { apiClient } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { getPairOptions, getPairsForTradeType } from "@/constants/pairs";

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
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [createForm, setCreateForm] = useState({
    traderName: "",
    tradeType: "FX",
    symbols: ["USD_JPY"] as string[],
    capitalJpy: 1000000,
    orderUnitLots: 1,
  });

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

  const handleCreate = async () => {
    if (!createForm.traderName) return;
    setCreating(true);
    try {
      await apiClient.post("/api/v1/traders", {
        traderName: createForm.traderName,
        tradeType: createForm.tradeType,
        symbols: createForm.symbols,
        capitalJpy: createForm.capitalJpy,
        orderUnitLots: createForm.orderUnitLots,
      });
      setCreateForm({
        traderName: "",
        tradeType: "FX",
        symbols: ["USD_JPY"],
        capitalJpy: 1000000,
        orderUnitLots: 1,
      });
      setShowCreate(false);
      await mutate();
    } catch {
      // Error handled by apiClient
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async () => {
    if (!selected) return;
    if (!window.confirm(`トレーダー「${selected.traderName}」を削除しますか？`)) return;
    setDeleting(true);
    try {
      await apiClient.del(`/api/v1/traders/${selected.id}`);
      setSelected(null);
      await mutate();
    } catch {
      // Error handled by apiClient
    } finally {
      setDeleting(false);
    }
  };

  const handleToggle = async () => {
    if (!selected) return;
    const action = selected.status === "running" ? "stop" : "start";
    setToggling(true);
    try {
      await apiClient.post(`/api/v1/traders/${selected.id}/${action}`);
      await mutate();
    } catch {
      alert(`${action === "start" ? "開始" : "停止"}に失敗しました`);
    } finally {
      setToggling(false);
    }
  };

  const merged = selected ? { ...selected, ...draft } : null;

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <div className="flex flex-1">
        {/* Left pane: trader list */}
        <aside className="w-72 border-r p-4">
          <TraderList
            traders={traders || []}
            activeId={selected?.id ?? null}
            onSelect={handleSelect}
          />
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-muted-foreground/30 py-2 text-sm text-muted-foreground hover:border-primary hover:text-primary"
          >
            <Plus className="h-4 w-4" />
            新規トレーダー追加
          </button>

          {/* Create trader form */}
          {showCreate && (
            <div className="mt-3 space-y-2 rounded-lg border bg-card p-3">
              <div>
                <label className="text-xs font-medium">名前</label>
                <Input
                  value={createForm.traderName}
                  onChange={(e) =>
                    setCreateForm((f) => ({ ...f, traderName: e.target.value }))
                  }
                  placeholder="トレーダー名"
                />
              </div>
              <div>
                <label className="text-xs font-medium">取引タイプ</label>
                <Select
                  value={createForm.tradeType}
                  options={[
                    { value: "FX", label: "FX" },
                    { value: "Crypto", label: "仮想通貨" },
                  ]}
                  onChange={(e) => {
                    const newType = e.target.value;
                    const defaultPair = getPairsForTradeType(newType)[0];
                    setCreateForm((f) => ({
                      ...f,
                      tradeType: newType,
                      symbols: [defaultPair],
                    }));
                  }}
                />
              </div>
              <div>
                <label className="text-xs font-medium">通貨ペア</label>
                <select
                  multiple
                  size={5}
                  value={createForm.symbols}
                  onChange={(e) => {
                    const selected = Array.from(
                      e.target.selectedOptions,
                      (opt) => opt.value
                    );
                    setCreateForm((f) => ({
                      ...f,
                      symbols: selected.length > 0 ? selected : f.symbols,
                    }));
                  }}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  {getPairOptions(createForm.tradeType).map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-muted-foreground">
                  Ctrl/Cmd+クリックで複数選択可
                </p>
              </div>
              <div>
                <label className="text-xs font-medium">資金(円)</label>
                <Input
                  type="number"
                  value={createForm.capitalJpy}
                  onChange={(e) =>
                    setCreateForm((f) => ({
                      ...f,
                      capitalJpy: Number(e.target.value),
                    }))
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium">注文ロット</label>
                <Input
                  type="number"
                  value={createForm.orderUnitLots}
                  onChange={(e) =>
                    setCreateForm((f) => ({
                      ...f,
                      orderUnitLots: Number(e.target.value),
                    }))
                  }
                />
              </div>
              <Button
                className="w-full"
                onClick={handleCreate}
                disabled={creating || !createForm.traderName}
              >
                {creating ? "作成中..." : "作成"}
              </Button>
            </div>
          )}
        </aside>

        {/* Right pane: settings tabs */}
        <main className="flex-1 p-6">
          {!merged ? (
            <p className="text-center text-muted-foreground">
              左のリストからトレーダーを選択してください
            </p>
          ) : (
            <div className="max-w-[900px]">
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-semibold">{merged.traderName}</h2>
                  <Badge
                    variant={
                      merged.status === "running"
                        ? "success"
                        : merged.status === "error" || merged.status === "halted"
                          ? "destructive"
                          : "secondary"
                    }
                  >
                    {merged.status === "running"
                      ? "稼働中"
                      : merged.status === "error"
                        ? "エラー"
                        : merged.status === "halted"
                          ? "停止(HALT)"
                          : "停止中"}
                  </Badge>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    onClick={handleToggle}
                    disabled={toggling}
                    className={
                      merged.status === "running"
                        ? "text-destructive hover:bg-destructive/10"
                        : "text-green-600 hover:bg-green-50"
                    }
                  >
                    {merged.status === "running" ? (
                      <Square className="mr-1.5 h-4 w-4" />
                    ) : (
                      <Play className="mr-1.5 h-4 w-4" />
                    )}
                    {toggling
                      ? "処理中..."
                      : merged.status === "running"
                        ? "停止"
                        : "開始"}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleDelete}
                    disabled={deleting}
                    className="text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 className="mr-1.5 h-4 w-4" />
                    {deleting ? "削除中..." : "削除"}
                  </Button>
                  <Button onClick={handleSave} disabled={saving}>
                    {saving ? "保存中..." : "保存"}
                  </Button>
                </div>
              </div>
              <Tabs defaultValue="basic">
                <TabsList>
                  <TabsTrigger value="basic">基本情報</TabsTrigger>
                  <TabsTrigger value="m1m2">M1-M2</TabsTrigger>
                  <TabsTrigger value="m3m4">M3-M4</TabsTrigger>
                  <TabsTrigger value="mx">MX</TabsTrigger>
                  <TabsTrigger value="safeguard">セーフガード</TabsTrigger>
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
                <TabsContent value="safeguard">
                  <SafeguardTab traderId={merged.id} />
                </TabsContent>
              </Tabs>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
