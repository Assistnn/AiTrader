/**
 * JSON Diff Viewer: side-by-side before/after comparison.
 * Reference: 01_画面仕様 (設定変更履歴画面)
 */

"use client";

interface JsonDiffViewerProps {
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}

export function JsonDiffViewer({ before, after }: JsonDiffViewerProps) {
  const allKeys = Array.from(
    new Set([...Object.keys(before), ...Object.keys(after)])
  ).sort();

  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <h4 className="text-sm font-semibold mb-2 text-red-600">Before</h4>
        <div className="bg-red-50 dark:bg-red-950 rounded p-3 text-xs font-mono space-y-1">
          {allKeys.map((key) => {
            const val = before[key];
            const changed =
              JSON.stringify(before[key]) !== JSON.stringify(after[key]);
            return (
              <div
                key={key}
                className={changed ? "text-red-700 font-bold" : ""}
              >
                {key}: {JSON.stringify(val)}
              </div>
            );
          })}
        </div>
      </div>
      <div>
        <h4 className="text-sm font-semibold mb-2 text-green-600">After</h4>
        <div className="bg-green-50 dark:bg-green-950 rounded p-3 text-xs font-mono space-y-1">
          {allKeys.map((key) => {
            const val = after[key];
            const changed =
              JSON.stringify(before[key]) !== JSON.stringify(after[key]);
            return (
              <div
                key={key}
                className={changed ? "text-green-700 font-bold" : ""}
              >
                {key}: {JSON.stringify(val)}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
