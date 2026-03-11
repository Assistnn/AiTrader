"use client";

/**
 * セーフガードタブ — トレーダー設定画面用
 * SafeguardSettingsPanelを再利用（制御コンポーネント）
 */

import { SafeguardSettingsPanel } from "@/components/dashboard/SafeguardSettingsPanel";

interface SafeguardTabProps {
  form: Record<string, unknown>;
  onChange: (path: string, value: unknown) => void;
}

export function SafeguardTab({ form, onChange }: SafeguardTabProps) {
  return (
    <div className="space-y-4 pt-4">
      <p className="text-sm text-muted-foreground">
        このトレーダーのセーフガードルール（SG-001〜SG-040）を設定します。
      </p>
      <SafeguardSettingsPanel form={form} onChange={onChange} />
    </div>
  );
}
