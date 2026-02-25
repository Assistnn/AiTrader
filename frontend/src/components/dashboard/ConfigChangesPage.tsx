/**
 * Config Changes Page.
 * Reference: 08_API仕様 Section 3-13, 01_画面仕様
 */

"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetcher } from "@/lib/api";
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

  const { data: changes } = useSWR<ConfigChangeItem[]>(
    `/api/v1/config-changes?page=${page}&perPage=20`,
    fetcher
  );

  const { data: detail } = useSWR<ConfigChangeDetail>(
    expandedId ? `/api/v1/config-changes/${expandedId}` : null,
    fetcher
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Config Changes</h1>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="p-3 text-left">Date</th>
                <th className="p-3 text-left">Trader</th>
                <th className="p-3 text-left">Type</th>
                <th className="p-3 text-left">Stage</th>
                <th className="p-3 text-left">Reason</th>
              </tr>
            </thead>
            <tbody>
              {changes?.map((c) => (
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
              {(!changes || changes.length === 0) && (
                <tr>
                  <td colSpan={5} className="p-6 text-center text-muted-foreground">
                    No config changes found
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
              Change #{detail.id} — {detail.configType}
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
