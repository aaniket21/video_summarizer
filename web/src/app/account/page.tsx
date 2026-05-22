"use client";

import React from "react";

import { AuthGuard } from "@/components/AuthGuard";
import { useAuth } from "@/hooks/useAuth";

export default function AccountPage() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-black dark:text-slate-50">
      <main className="mx-auto max-w-3xl px-5 py-10">
        <AuthGuard>
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
            <div className="text-sm text-[var(--muted)]">Account</div>
            <div className="text-2xl font-semibold mt-2">Welcome back.</div>
            <div className="mt-4 text-sm text-[var(--muted)]">Signed in as</div>
            <div className="font-medium mt-1">{user?.email || "Unknown user"}</div>
          </div>
        </AuthGuard>
      </main>
    </div>
  );
}
