"use client";

import React, { useState } from "react";

import { AuthGuard } from "@/components/AuthGuard";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";

export default function AccountPage() {
  const { user, accessToken } = useAuth();
  const [billingBusy, setBillingBusy] = useState(false);
  const [billingError, setBillingError] = useState("");

  async function startCheckout() {
    setBillingError("");
    setBillingBusy(true);
    try {
      const res = await apiFetch(
        "/api/v1/billing/checkout",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plan: "student" }),
        },
        accessToken,
      );

      const payload = await res.json();
      if (!res.ok) {
        setBillingError(payload?.error || "Unable to start checkout.");
        return;
      }

      if (payload?.url) {
        window.location.href = String(payload.url);
      } else {
        setBillingError("Checkout URL missing from response.");
      }
    } catch (error) {
      setBillingError((error as Error).message || "Unable to start checkout.");
    } finally {
      setBillingBusy(false);
    }
  }

  async function openPortal() {
    setBillingError("");
    setBillingBusy(true);
    try {
      const res = await apiFetch(
        "/api/v1/billing/portal",
        { method: "POST" },
        accessToken,
      );
      const payload = await res.json();
      if (!res.ok) {
        setBillingError(payload?.error || "Unable to open billing portal.");
        return;
      }

      if (payload?.url) {
        window.location.href = String(payload.url);
      } else {
        setBillingError("Portal URL missing from response.");
      }
    } catch (error) {
      setBillingError((error as Error).message || "Unable to open billing portal.");
    } finally {
      setBillingBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-black dark:text-slate-50">
      <main className="mx-auto max-w-3xl px-5 py-10">
        <AuthGuard>
          <div className="space-y-6">
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
              <div className="text-sm text-[var(--muted)]">Account</div>
              <div className="text-2xl font-semibold mt-2">Welcome back.</div>
              <div className="mt-4 text-sm text-[var(--muted)]">Signed in as</div>
              <div className="font-medium mt-1">{user?.email || "Unknown user"}</div>
            </div>

            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
              <div className="text-sm text-[var(--muted)]">Billing</div>
              <div className="text-xl font-semibold mt-2">Student plan</div>
              <div className="mt-2 text-sm text-[var(--muted)]">
                Unlock longer videos, more exports, and higher monthly limits.
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={billingBusy}
                  onClick={startCheckout}
                  className="rounded-xl bg-slate-900 text-white px-4 py-2 text-sm hover:bg-slate-800 transition disabled:opacity-60"
                >
                  Upgrade to Student
                </button>
                <button
                  type="button"
                  disabled={billingBusy}
                  onClick={openPortal}
                  className="rounded-xl border border-[var(--border)] px-4 py-2 text-sm hover:bg-white/10 transition disabled:opacity-60"
                >
                  Manage billing
                </button>
              </div>
              {billingError && <div className="mt-3 text-xs text-red-500">{billingError}</div>}
            </div>
          </div>
        </AuthGuard>
      </main>
    </div>
  );
}
