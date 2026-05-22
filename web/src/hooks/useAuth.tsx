"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";

import { getSupabaseClient, isSupabaseConfigured } from "@/lib/supabaseClient";

export type AuthStatus = "loading" | "guest" | "authed";

export type AuthActionResult = { error?: string };

export type AuthContextValue = {
  status: AuthStatus;
  user: User | null;
  session: Session | null;
  accessToken: string;
  isConfigured: boolean;
  signInWithGoogle: () => Promise<AuthActionResult>;
  signInWithPassword: (email: string, password: string) => Promise<AuthActionResult>;
  signUpWithPassword: (email: string, password: string) => Promise<AuthActionResult>;
  signOut: () => Promise<AuthActionResult>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const supabase = getSupabaseClient();
  const configured = isSupabaseConfigured();

  const [status, setStatus] = useState<AuthStatus>(configured ? "loading" : "guest");
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!supabase) {
      setStatus("guest");
      return;
    }

    let isMounted = true;

    supabase.auth.getSession().then(({ data }) => {
      if (!isMounted) return;
      const nextSession = data.session ?? null;
      setSession(nextSession);
      setUser(nextSession?.user ?? null);
      setStatus(nextSession ? "authed" : "guest");
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (!isMounted) return;
      setSession(nextSession);
      setUser(nextSession?.user ?? null);
      setStatus(nextSession ? "authed" : "guest");
    });

    return () => {
      isMounted = false;
      subscription.subscription?.unsubscribe();
    };
  }, [supabase]);

  const signInWithGoogle = useCallback(async (): Promise<AuthActionResult> => {
    if (!supabase) return { error: "Supabase is not configured." };
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
    });
    return error ? { error: error.message } : {};
  }, [supabase]);

  const signInWithPassword = useCallback(
    async (email: string, password: string): Promise<AuthActionResult> => {
      if (!supabase) return { error: "Supabase is not configured." };
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      return error ? { error: error.message } : {};
    },
    [supabase],
  );

  const signUpWithPassword = useCallback(
    async (email: string, password: string): Promise<AuthActionResult> => {
      if (!supabase) return { error: "Supabase is not configured." };
      const { error } = await supabase.auth.signUp({ email, password });
      return error ? { error: error.message } : {};
    },
    [supabase],
  );

  const signOut = useCallback(async (): Promise<AuthActionResult> => {
    if (!supabase) return { error: "Supabase is not configured." };
    const { error } = await supabase.auth.signOut();
    return error ? { error: error.message } : {};
  }, [supabase]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      session,
      accessToken: session?.access_token ?? "",
      isConfigured: configured,
      signInWithGoogle,
      signInWithPassword,
      signUpWithPassword,
      signOut,
    }),
    [status, user, session, configured, signInWithGoogle, signInWithPassword, signUpWithPassword, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    return {
      status: "guest",
      user: null,
      session: null,
      accessToken: "",
      isConfigured: false,
      signInWithGoogle: async () => ({ error: "Auth context unavailable." }),
      signInWithPassword: async () => ({ error: "Auth context unavailable." }),
      signUpWithPassword: async () => ({ error: "Auth context unavailable." }),
      signOut: async () => ({ error: "Auth context unavailable." }),
    };
  }
  return ctx;
}
