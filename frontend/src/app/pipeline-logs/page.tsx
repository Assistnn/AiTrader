"use client";

import { Header } from "@/components/common/Header";
import { PipelineLogsPage } from "@/components/dashboard/PipelineLogsPage";

export default function PipelineLogsRoute() {
  return (
    <>
      <Header />
      <main className="container mx-auto p-6">
        <PipelineLogsPage />
      </main>
    </>
  );
}
