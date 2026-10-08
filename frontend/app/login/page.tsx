"use client";

import { useEffect } from "react";
import { signIn } from "@/lib/auth";

export default function LoginPage() {
  useEffect(() => {
    void signIn();
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <p>Redirecting to sign in...</p>
    </main>
  );
}
