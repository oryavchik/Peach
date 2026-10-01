"use client";

import { useEffect, useState } from "react";

const REGION = process.env.NEXT_PUBLIC_COGNITO_REGION ?? "us-east-1";
const CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? "";

const STORAGE_KEY = "peach-auth";

export type Session = {
  idToken: string;
  accessToken: string;
  refreshToken?: string;
  email: string;
  name: string;
};

function readSession(): Session | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

function decodeJwt(token: string): Record<string, unknown> {
  const part = token.split(".")[1];
  if (!part) return {};

  const normalized = part.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(
    normalized.length + ((4 - (normalized.length % 4)) % 4),
    "=",
  );

  return JSON.parse(atob(padded));
}

export async function signIn(
  email: string,
  password: string,
): Promise<Session> {
  const response = await fetch(
    `https://cognito-idp.${REGION}.amazonaws.com/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
      },
      body: JSON.stringify({
        AuthFlow: "USER_PASSWORD_AUTH",
        ClientId: CLIENT_ID,
        AuthParameters: {
          USERNAME: email,
          PASSWORD: password,
        },
      }),
    },
  );

  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.message ?? "Sign in failed");
  }

  const auth = body.AuthenticationResult;
  if (!auth?.IdToken || !auth?.AccessToken) {
    throw new Error("Authentication failed");
  }

  const claims = decodeJwt(auth.IdToken);

  const session: Session = {
    idToken: auth.IdToken,
    accessToken: auth.AccessToken,
    refreshToken: auth.RefreshToken,
    email: typeof claims.email === "string" ? claims.email : email,
    name:
      typeof claims.name === "string"
        ? claims.name
        : typeof claims.email === "string"
          ? claims.email
          : email,
  };

  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  window.dispatchEvent(new Event("peach-auth-change"));

  return session;
}

export async function signUp(
  email: string,
  password: string,
  name: string,
): Promise<void> {
  const response = await fetch(
    `https://cognito-idp.${REGION}.amazonaws.com/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityProviderService.SignUp",
      },
      body: JSON.stringify({
        ClientId: CLIENT_ID,
        Username: email,
        Password: password,
        UserAttributes: [
          { Name: "email", Value: email },
          { Name: "name", Value: name },
        ],
      }),
    },
  );

  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.message ?? "Sign up failed");
  }
}

export async function confirmSignUp(
  email: string,
  code: string,
): Promise<void> {
  const response = await fetch(
    `https://cognito-idp.${REGION}.amazonaws.com/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityProviderService.ConfirmSignUp",
      },
      body: JSON.stringify({
        ClientId: CLIENT_ID,
        Username: email,
        ConfirmationCode: code,
      }),
    },
  );

  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.message ?? "Confirmation failed");
  }
}

export async function getIdToken(): Promise<string | null> {
  return readSession()?.idToken ?? null;
}

export function signOut(): void {
  if (typeof window === "undefined") return;

  localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event("peach-auth-change"));
}

export function useSession(): Session | null {
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    const update = () => setSession(readSession());

    update();

    window.addEventListener("storage", update);
    window.addEventListener("peach-auth-change", update);

    return () => {
      window.removeEventListener("storage", update);
      window.removeEventListener("peach-auth-change", update);
    };
  }, []);

  return session;
}
