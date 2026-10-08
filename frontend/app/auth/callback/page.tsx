"use client";

import { useEffect, useRef, useState } from "react";
import { handleSignInCallback } from "@/lib/auth";

export default function AuthCallbackPage() {
  const started = useRef(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    const finishSignIn = async () => {
      try {
        await handleSignInCallback();
        window.location.replace("/home/");
      } catch (err) {
        console.error("Cognito callback failed:", err);

        setError(err instanceof Error ? err.message : "Authentication failed");
      }
    };

    void finishSignIn();
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-4">
        <div className="grid size-12 place-items-center rounded-xl bg-foreground text-xl font-semibold text-background">
          P
        </div>

        {error ? (
          <>
            <h1 className="text-xl font-semibold">Sign in failed</h1>
            <p className="max-w-md text-center text-sm text-muted-foreground">
              {error}
            </p>
            <a href="/login/" className="text-sm underline">
              Try again
            </a>
          </>
        ) : (
          <>
            <div className="text-center">
              <h1 className="text-xl font-semibold">Signing you in</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Just a moment...
              </p>
            </div>

            <div className="size-5 animate-spin rounded-full border-2 border-muted border-t-foreground" />
          </>
        )}
      </div>
    </main>
  );
}
