"use client";

import { useEffect, useState, type FormEvent } from "react";
import { getIdToken, isFreeCloud, signIn } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  useEffect(() => {
    if (!isFreeCloud) void signIn();
    else
      void getIdToken().then((token) => {
        if (token) window.location.replace("/home/");
      });
  }, []);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const password = new FormData(event.currentTarget).get("password");
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(result.error ?? "Could not sign in. Try again.");
      }
      window.location.replace("/home/");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not sign in.");
    } finally {
      setPending(false);
    }
  }

  if (isFreeCloud)
    return (
      <main className="flex min-h-screen items-center justify-center px-6">
        <section className="w-full max-w-sm space-y-6 rounded-xl border bg-card p-8 shadow-sm">
          <div className="space-y-2">
            <div className="grid size-9 place-items-center rounded-lg bg-foreground font-semibold text-background">
              P
            </div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Sign in to Peach
            </h1>
            <p className="text-sm text-muted-foreground">
              Use your demo password to open your board and meetings.
            </p>
          </div>
          <form onSubmit={login} className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </div>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <Button className="w-full" disabled={pending}>
              {pending ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </section>
      </main>
    );

  return (
    <main className="flex min-h-screen items-center justify-center">
      <p>Redirecting to sign in...</p>
    </main>
  );
}
