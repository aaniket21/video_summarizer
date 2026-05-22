"use client";

import React from "react";

import { useAuth } from "@/hooks/useAuth";
import { AuthPanel } from "@/components/AuthPanel";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 text-sm text-[var(--muted)]">
        Loading your account...
      </div>
    );
  }

  if (status === "guest") {
    return (
      <div className="space-y-4">
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
          <div className="text-sm text-[var(--muted)]">Guest mode</div>
          <div className="text-lg font-semibold mt-2">Sign in to access this page.</div>
        </div>
        <AuthPanel />
      </div>
    );
  }

  return <>{children}</>;
}
