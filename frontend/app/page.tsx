import { Suspense } from "react";
import { CommandCenter } from "@/components/CommandCenter";
import { LoadingPanel } from "@/components/LoadingPanel";

export default function HomePage() {
  return (
    <Suspense fallback={<LoadingPanel />}>
      <CommandCenter />
    </Suspense>
  );
}
