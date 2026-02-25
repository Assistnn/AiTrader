/**
 * Pipeline Logs Page.
 * Reference: 08_API仕様 Section 3-12, 01_画面仕様
 */

"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetcher } from "@/lib/api";

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

function stageColor(stage: string): string {
  const colors: Record<string, string> = {
    m1: "bg-blue-100 text-blue-800",
    m2: "bg-green-100 text-green-800",
    m3: "bg-yellow-100 text-yellow-800",
    m4: "bg-purple-100 text-purple-800",
    guard: "bg-red-100 text-red-800",
  };
  return colors[stage] || "bg-gray-100 text-gray-800";
}

export function PipelineLogsPage() {
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: logs } = useSWR<PipelineLog[]>(
    `/api/v1/pipeline-logs?page=${page}&perPage=20`,
    fetcher
  );

  const { data: detail } = useSWR<PipelineLogDetail[]>(
    expandedId ? `/api/v1/pipeline-logs/${expandedId}` : null,
    fetcher
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Pipeline Logs</h1>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="p-3 text-left">Timestamp</th>
                <th className="p-3 text-left">Trader</th>
                <th className="p-3 text-left">Pair</th>
                <th className="p-3 text-left">Stage</th>
                <th className="p-3 text-left">Mode</th>
                <th className="p-3 text-right">Elapsed</th>
              </tr>
            </thead>
            <tbody>
              {logs?.map((log) => (
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
                    <Badge className={stageColor(log.stage)}>{log.stage}</Badge>
                  </td>
                  <td className="p-3">{log.mode || "-"}</td>
                  <td className="p-3 text-right">
                    {log.elapsedMs != null ? `${log.elapsedMs}ms` : "-"}
                  </td>
                </tr>
              ))}
              {(!logs || logs.length === 0) && (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-muted-foreground">
                    No pipeline logs found
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
              Execution: {expandedId.slice(0, 8)}...
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {detail.map((d) => (
              <div key={d.id} className="border rounded p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Badge className={stageColor(d.stage)}>{d.stage}</Badge>
                  <span className="text-sm text-muted-foreground">
                    {d.elapsedMs != null ? `${d.elapsedMs}ms` : ""}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs font-semibold mb-1">Output</p>
                    <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-40">
                      {JSON.stringify(d.outputSnapshot, null, 2)}
                    </pre>
                  </div>
                  <div>
                    <p className="text-xs font-semibold mb-1">Config</p>
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
      <div className="flex gap-2 justify-center">
        <button
          className="px-3 py-1 border rounded disabled:opacity-50"
          disabled={page <= 1}
          onClick={() => setPage((p) => p - 1)}
        >
          Prev
        </button>
        <span className="px-3 py-1">Page {page}</span>
        <button
          className="px-3 py-1 border rounded"
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
