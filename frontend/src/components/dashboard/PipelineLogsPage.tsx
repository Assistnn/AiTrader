/**
 * パイプラインログ画面
 * Reference: 08_API仕様 Section 3-12, 01_画面仕様
 */

"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetcher, paginatedFetcher } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface PipelineLog {
  id: number;
  executionId: string;
  traderId: number;
  pair: string;
  timestamp: string;
  stage: string;
  mode: string | null;
  elapsedMs: number | null;
  createdAt: string;
}

interface PipelineLogDetail {
  id: number;
  executionId: string;
  traderId: number;
  pair: string;
  timestamp: string;
  stage: string;
  mode: string | null;
  inputSnapshot: Record<string, unknown>;
  outputSnapshot: Record<string, unknown>;
  configSnapshot: Record<string, unknown>;
  elapsedMs: number | null;
  createdAt: string;
}

const stageLabels: Record<string, string> = {
  m1: "M1: 方向判定",
  m2: "M2: セットアップ",
  m3: "M3: エントリー",
  m4: "M4: 退出",
  guard: "ガード",
};

function stageColor(stage: string): string {
  const colors: Record<string, string> = {
    m1: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    m2: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    m3: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
    m4: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
    guard: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  };
  return colors[stage] || "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200";
}

export function PipelineLogsPage() {
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: result } = useSWR(
    `/api/v1/pipeline-logs?page=${page}&perPage=20`,
    paginatedFetcher<PipelineLog>
  );

  const logs = result?.data ?? [];
  const totalPages = result?.pagination?.totalPages ?? 1;
  const totalItems = result?.pagination?.totalItems ?? 0;

  const { data: detail } = useSWR<PipelineLogDetail[]>(
    expandedId ? `/api/v1/pipeline-logs/${expandedId}` : null,
    fetcher
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">パイプラインログ</h1>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="p-3 text-left">日時</th>
                <th className="p-3 text-left">トレーダー</th>
                <th className="p-3 text-left">通貨ペア</th>
                <th className="p-3 text-left">ステージ</th>
                <th className="p-3 text-left">モード</th>
                <th className="p-3 text-right">処理時間</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr
                  key={log.id}
                  className="border-t cursor-pointer hover:bg-muted/30"
                  onClick={() =>
                    setExpandedId(
                      expandedId === log.executionId ? null : log.executionId
                    )
                  }
                >
                  <td className="p-3 font-mono text-xs">
                    {new Date(log.timestamp).toLocaleString("ja-JP")}
                  </td>
                  <td className="p-3">{log.traderId}</td>
                  <td className="p-3">{log.pair}</td>
                  <td className="p-3">
                    <Badge className={stageColor(log.stage)}>
                      {stageLabels[log.stage] || log.stage}
                    </Badge>
                  </td>
                  <td className="p-3">{log.mode || "-"}</td>
                  <td className="p-3 text-right">
                    {log.elapsedMs != null ? `${log.elapsedMs}ms` : "-"}
                  </td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-muted-foreground">
                    パイプラインログがありません
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Expanded detail */}
      {expandedId && detail && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              実行ID: {expandedId.slice(0, 8)}...
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {detail.map((d) => (
              <div key={d.id} className="border rounded p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Badge className={stageColor(d.stage)}>
                    {stageLabels[d.stage] || d.stage}
                  </Badge>
                  <span className="text-sm text-muted-foreground">
                    {d.elapsedMs != null ? `${d.elapsedMs}ms` : ""}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs font-semibold mb-1">出力</p>
                    <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-40">
                      {JSON.stringify(d.outputSnapshot, null, 2)}
                    </pre>
                  </div>
                  <div>
                    <p className="text-xs font-semibold mb-1">設定</p>
                    <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-40">
                      {JSON.stringify(d.configSnapshot, null, 2)}
                    </pre>
                  </div>
                </div>
              </div>
            ))}
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
