"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { SiteHeader } from "@/components/site-header";
import { getIdToken } from "@/lib/auth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    getIdToken().then((token) => {
      if (!token) {
        router.replace("/");
        return;
      }

      setReady(true);
    });
  }, [router]);

  if (!ready) return null;

  return (
    <>
      <SiteHeader />
      <main className="flex-1">{children}</main>
    </>
  );
}
