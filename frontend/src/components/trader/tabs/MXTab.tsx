"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";

interface MXConfig {
  evaluationMode: string;
  scoreWeights: { direction: number; setup: number; execution: number };
  scoreThreshold: number;
}

interface MXTabProps {
  mx: MXConfig;
  onChange: (field: string, value: unknown) => void;
}

export function MXTab({ mx, onChange }: MXTabProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">MX: Integrated Judgment</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="text-xs font-medium">Evaluation Mode</label>
          <Select
            value={mx.evaluationMode}
            options={[
              { value: "all", label: "All stages must pass" },
              { value: "dir+setup", label: "Direction + Setup" },
              { value: "score", label: "Score-based" },
            ]}
            onChange={(e) => onChange("evaluationMode", e.target.value)}
          />
        </div>

        {mx.evaluationMode === "score" && (
          <>
            <div>
              <label className="text-xs font-medium">Score Weights</label>
              <div className="mt-2 grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground">
                    Direction
                  </label>
                  <Input
                    type="number"
                    min={0}
                    max={1}
                    step={0.1}
                    value={mx.scoreWeights.direction}
                    onChange={(e) =>
                      onChange("scoreWeights.direction", Number(e.target.value))
                    }
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Setup</label>
                  <Input
                    type="number"
                    min={0}
                    max={1}
                    step={0.1}
                    value={mx.scoreWeights.setup}
                    onChange={(e) =>
                      onChange("scoreWeights.setup", Number(e.target.value))
                    }
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">
                    Execution
                  </label>
                  <Input
                    type="number"
                    min={0}
                    max={1}
                    step={0.1}
                    value={mx.scoreWeights.execution}
                    onChange={(e) =>
                      onChange("scoreWeights.execution", Number(e.target.value))
                    }
                  />
                </div>
              </div>
            </div>
            <div>
              <label className="text-xs font-medium">Score Threshold</label>
              <Input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={mx.scoreThreshold}
                onChange={(e) =>
                  onChange("scoreThreshold", Number(e.target.value))
                }
              />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
