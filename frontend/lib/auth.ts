"use client";

import { useEffect, useState } from "react";
import { User, UserManager, WebStorageStateStore } from "oidc-client-ts";

const REGION = process.env.NEXT_PUBLIC_COGNITO_REGION ?? "us-east-1";
const USER_POOL_ID =
  process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? "us-east-1_0mtP1IR3E";
const CLIENT_ID =
  process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? "2p3i99e7rbukboqojfrdmdsfcl";
const DOMAIN =
  process.env.NEXT_PUBLIC_COGNITO_DOMAIN ??
  "peach-506126098984.auth.us-east-1.amazoncognito.com";

export type Session = {
  idToken: string;
  accessToken: string;
  email: string;
  name: string;
};

let manager: UserManager | null = null;

function getUserManager(): UserManager {
  if (typeof window === "undefined") {
    throw new Error("Auth is only available in the browser");
  }

  if (!manager) {
    manager = new UserManager({
      authority: `https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}`,
      client_id: CLIENT_ID,
      redirect_uri: `${window.location.origin}/auth/callback/`,
      response_type: "code",
      scope: "openid email profile",
      userStore: new WebStorageStateStore({
        store: window.localStorage,
      }),
    });
  }

  return manager;
}

function toSession(user: User | null): Session | null {
  if (!user || user.expired) return null;

  const email =
    typeof user.profile.email === "string" ? user.profile.email : "";

  const isGoogleUser = Array.isArray(user.profile.identities);

  const name =
    isGoogleUser && typeof user.profile.name === "string" && user.profile.name
      ? user.profile.name
      : email;

  return {
    idToken: user.id_token ?? "",
    accessToken: user.access_token,
    email,
    name,
  };
}

export async function signIn(): Promise<void> {
  await getUserManager().signinRedirect();
}

export async function handleSignInCallback(): Promise<Session | null> {
  const user = await getUserManager().signinRedirectCallback();
  window.dispatchEvent(new Event("peach-auth-change"));
  return toSession(user);
}

export async function getIdToken(): Promise<string | null> {
  const user = await getUserManager().getUser();
  return user?.id_token ?? null;
}

export async function signOut(): Promise<void> {
  const auth = getUserManager();

  await auth.removeUser();

  const logoutUri = `${window.location.origin}/`;

  window.location.href =
    `https://${DOMAIN}/logout` +
    `?client_id=${encodeURIComponent(CLIENT_ID)}` +
    `&logout_uri=${encodeURIComponent(logoutUri)}`;
}

export function useSession(): Session | null {
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    const update = async () => {
      const user = await getUserManager().getUser();
      setSession(toSession(user));
    };

    void update();

    window.addEventListener("peach-auth-change", update);
    window.addEventListener("storage", update);

    return () => {
      window.removeEventListener("peach-auth-change", update);
      window.removeEventListener("storage", update);
    };
  }, []);

  return session;
}
