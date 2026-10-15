import { Suspense } from "react";
import { AgendaEditor } from "@/components/agenda-editor";

export default function AgendaPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading agenda…</p>}>
      <AgendaEditor />
    </Suspense>
  );
}
