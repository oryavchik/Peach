import Link from "next/link";

import { Button } from "@/components/ui/button";

export const metadata = { title: "Home | Peach" };

export default function HomePage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-12 sm:px-8">
      <div className="max-w-xl space-y-4">
        <h1 className="text-3xl font-semibold tracking-tight">
          Welcome to Peach
        </h1>

        <p className="text-muted-foreground">
          Manage your tasks and keep track of their progress.
        </p>

        <Button asChild>
          <Link href="/items">Open task board</Link>
        </Button>
      </div>
    </div>
  );
}
