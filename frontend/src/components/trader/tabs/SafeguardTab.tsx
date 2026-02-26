"use client";

/**
 * セーフガードタブ — トレーダー設定画面用
 * SafeguardSettingsPanelを再利用（トレーダーID固定）
 */

import { SafeguardSettingsPanel } from "@/components/dashboard/SafeguardSettingsPanel";

interface SafeguardTabProps {
  traderId: number;
}

export function SafeguardTab({ traderId }: SafeguardTabProps) {
  return (
    <div className="space-y-4 pt-4">
      <p className="text-sm text-muted-foreground">
        このトレーダーのセーフガードルール（SG-001〜SG-040）を設定します。
      </p>
      <SafeguardSettingsPanel traderId={traderId} />
    </div>
  );
}
