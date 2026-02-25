"use client";

import { Header } from "@/components/common/Header";
import { ConfigChangesPage } from "@/components/dashboard/ConfigChangesPage";

export default function ConfigChangesRoute() {
  return (
    <>
      <Header />
      <main className="container mx-auto p-6">
        <ConfigChangesPage />
      </main>
    </>
  );
}
