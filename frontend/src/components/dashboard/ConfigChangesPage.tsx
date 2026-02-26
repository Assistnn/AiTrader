/**
 * 設定変更履歴画面
 * Reference: 08_API仕様 Section 3-13, 01_画面仕様
 */

"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetcher, paginatedFetcher } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { JsonDiffViewer } from "@/components/dashboard/JsonDiffViewer";

interface ConfigChangeItem {
  id: number;
  traderId: number;
  configType: string;
  stage: string | null;
  changedAt: string;
  changedBy: number;
  changeReason: string | null;
}

interface ConfigChangeDetail extends ConfigChangeItem {
  configBefore: Record<string, unknown>;
  configAfter: Record<string, unknown>;
}

export function ConfigChangesPage() {
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { data: result } = useSWR(
    `/api/v1/config-changes?page=${page}&perPage=20`,
    paginatedFetcher<ConfigChangeItem>
  );

  const changes = result?.data ?? [];
  const totalPages = result?.pagination?.totalPages ?? 1;
  const totalItems = result?.pagination?.totalItems ?? 0;

  const { data: detail } = useSWR<ConfigChangeDetail>(
    expandedId ? `/api/v1/config-changes/${expandedId}` : null,
    fetcher
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">設定変更履歴</h1>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="p-3 text-left">日時</th>
                <th className="p-3 text-left">トレーダー</th>
                <th className="p-3 text-left">種別</th>
                <th className="p-3 text-left">ステージ</th>
                <th className="p-3 text-left">変更理由</th>
              </tr>
            </thead>
            <tbody>
              {changes.map((c) => (
                <tr
                  key={c.id}
                  className="border-t cursor-pointer hover:bg-muted/30"
                  onClick={() =>
                    setExpandedId(expandedId === c.id ? null : c.id)
                  }
                >
                  <td className="p-3 font-mono text-xs">
                    {new Date(c.changedAt).toLocaleString("ja-JP")}
                  </td>
                  <td className="p-3">{c.traderId}</td>
                  <td className="p-3">
                    <Badge variant="outline">{c.configType}</Badge>
                  </td>
                  <td className="p-3">{c.stage || "-"}</td>
                  <td className="p-3 text-muted-foreground">
                    {c.changeReason || "-"}
                  </td>
                </tr>
              ))}
              {changes.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-6 text-center text-muted-foreground">
                    設定変更履歴がありません
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Detail diff */}
      {expandedId && detail && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              変更 #{detail.id} — {detail.configType}
              {detail.stage ? ` / ${detail.stage}` : ""}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <JsonDiffViewer
              before={detail.configBefore}
              after={detail.configAfter}
            />
          </CardContent>
        </Card>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            前へ
          </Button>
          <span className="text-sm text-muted-foreground">
            {page} / {totalPages}
            {totalItems > 0 && ` (${totalItems}件)`}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            次へ
          </Button>
        </div>
      )}
    </div>
  );
}
