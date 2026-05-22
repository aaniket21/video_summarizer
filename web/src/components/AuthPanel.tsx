"use client";

import React, { useState } from "react";

import { useAuth } from "@/hooks/useAuth";

export type AuthPanelStatus = "guest" | "authed" | "loading";

type AuthPanelViewProps = {
  status: AuthPanelStatus;
  email?: string;
  showEmailActions?: boolean;
  onGoogle: () => void;
  onEmailSignIn: () => void;
  onEmailSignUp: () => void;
  onSignOut: () => void;
};

export function AuthPanelView({
  status,
  email,
  showEmailActions = true,
  onGoogle,
  onEmailSignIn,
  onEmailSignUp,
  onSignOut,
}: AuthPanelViewProps) {
  if (status === "loading") {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 text-sm text-[var(--muted)]">
        Loading account...
      </div>
    );
  }

  if (status === "authed") {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="text-sm text-[var(--muted)]">Signed in as</div>
        <div className="font-medium mt-1">{email || "Unknown user"}</div>
        <button
          type="button"
          onClick={onSignOut}
          className="mt-4 w-full rounded-xl border border-[var(--border)] px-4 py-2 text-sm hover:bg-white/10 transition"
        >
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="text-sm text-[var(--muted)]">Guest mode</div>
      <div className="font-medium mt-1">Sign in for history and premium exports.</div>

      <div className="mt-4 grid gap-2">
        <button
          type="button"
          onClick={onGoogle}
          className="w-full rounded-xl bg-slate-900 text-white px-4 py-2 text-sm hover:bg-slate-800 transition"
        >
          Continue with Google
        </button>
        {showEmailActions && (
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={onEmailSignIn}
              className="rounded-xl border border-[var(--border)] px-3 py-2 text-sm hover:bg-white/10 transition"
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={onEmailSignUp}
              className="rounded-xl border border-[var(--border)] px-3 py-2 text-sm hover:bg-white/10 transition"
            >
              Create account
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function AuthPanel() {
  const {
    status,
    user,
    isConfigured,
    signInWithGoogle,
    signInWithPassword,
    signUpWithPassword,
    signOut,
  } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleGoogle() {
    setBusy(true);
    const result = await signInWithGoogle();
    setError(result.error || "");
    setBusy(false);
  }

  async function handleEmailSignIn() {
    if (!email || !password) {
      setError("Email and password are required.");
      return;
    }
    setBusy(true);
    const result = await signInWithPassword(email, password);
    setError(result.error || "");
    setBusy(false);
  }

  async function handleEmailSignUp() {
    if (!email || !password) {
      setError("Email and password are required.");
      return;
    }
    setBusy(true);
    const result = await signUpWithPassword(email, password);
    setError(result.error || "");
    setBusy(false);
  }

  async function handleSignOut() {
    setBusy(true);
    const result = await signOut();
    setError(result.error || "");
    setBusy(false);
  }

  if (!isConfigured) {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 text-sm text-[var(--muted)]">
        Supabase is not configured. Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY to enable auth.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <AuthPanelView
        status={status}
        email={user?.email}
        showEmailActions={false}
        onGoogle={handleGoogle}
        onEmailSignIn={handleEmailSignIn}
        onEmailSignUp={handleEmailSignUp}
        onSignOut={handleSignOut}
      />

      {status === "guest" && (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="text-sm font-medium">Email login</div>
          <div className="mt-3 grid gap-3">
            <label className="text-xs text-[var(--muted)]">
              Email
              <input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                type="email"
                placeholder="you@example.com"
                className="mt-1 w-full rounded-xl border border-[var(--border)] bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500/30"
              />
            </label>
            <label className="text-xs text-[var(--muted)]">
              Password
              <input
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                type="password"
                placeholder="••••••••"
                className="mt-1 w-full rounded-xl border border-[var(--border)] bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500/30"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={handleEmailSignIn}
                className="rounded-xl border border-[var(--border)] px-3 py-2 text-sm hover:bg-white/10 transition disabled:opacity-60"
              >
                Sign in
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={handleEmailSignUp}
                className="rounded-xl border border-[var(--border)] px-3 py-2 text-sm hover:bg-white/10 transition disabled:opacity-60"
              >
                Create account
              </button>
            </div>
            {error && <div className="text-xs text-red-500">{error}</div>}
          </div>
        </div>
      )}
    </div>
  );
}
