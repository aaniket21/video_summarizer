"use client";

import React, { useEffect, useState } from "react";

import { AuthGuard } from "@/components/AuthGuard";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";

export default function AccountPage() {
  const { user, accessToken } = useAuth();
  const [billingBusy, setBillingBusy] = useState(false);
  const [billingError, setBillingError] = useState("");
  const [integrationNotice, setIntegrationNotice] = useState("");
  const [studentStatus, setStudentStatus] = useState<string>("unknown");
  const [studentRef, setStudentRef] = useState<string>("");
  const [studentBusy, setStudentBusy] = useState(false);

  const [teams, setTeams] = useState<Array<{ id: string; name: string; plan: string }>>([]);
  const [teamLoading, setTeamLoading] = useState(false);
  const [teamError, setTeamError] = useState("");
  const [newTeamName, setNewTeamName] = useState("");
  const [selectedTeamId, setSelectedTeamId] = useState<string>("");
  const [teamMembers, setTeamMembers] = useState<Array<{ id: string; email: string; role: string; status: string }>>([]);
  const [memberEmail, setMemberEmail] = useState("");

  const [apiKeys, setApiKeys] = useState<Array<{ id: string; label: string; key_prefix: string; team_id?: string | null }>>([]);
  const [apiKeyLabel, setApiKeyLabel] = useState("");
  const [apiKeySecret, setApiKeySecret] = useState<string | null>(null);

  const [webhooks, setWebhooks] = useState<Array<{ id: string; url: string; events: string[]; team_id?: string | null }>>([]);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookEvents, setWebhookEvents] = useState("job.completed, job.failed");

  async function startCheckout(plan: "student" | "pro" | "team") {
    setBillingError("");
    setBillingBusy(true);
    try {
      const res = await apiFetch(
        "/api/v1/billing/checkout",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plan }),
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

  async function refreshStudentStatus() {
    if (!accessToken) return;
    try {
      const res = await apiFetch("/api/v1/billing/student/status", {}, accessToken);
      const payload = await res.json();
      if (!res.ok) {
        setStudentStatus("unknown");
        return;
      }
      setStudentStatus(payload?.status || "unknown");
      setStudentRef(payload?.reference_id || "");
    } catch {
      setStudentStatus("unknown");
    }
  }

  async function startStudentVerification() {
    if (!accessToken) return;
    setStudentBusy(true);
    try {
      const res = await apiFetch("/api/v1/billing/student/verify", { method: "POST" }, accessToken);
      const payload = await res.json();
      if (!res.ok) {
        setBillingError(payload?.error || "Unable to start verification.");
        return;
      }
      setStudentStatus(payload?.status || "pending");
      setStudentRef(payload?.reference_id || "");
      if (payload?.verification_url) {
        window.open(String(payload.verification_url), "_blank");
      }
    } catch (error) {
      setBillingError((error as Error).message || "Unable to start verification.");
    } finally {
      setStudentBusy(false);
    }
  }

  async function loadTeams() {
    if (!accessToken) return;
    setTeamLoading(true);
    setTeamError("");
    try {
      const res = await apiFetch("/api/v1/teams", {}, accessToken);
      const payload = await res.json();
      if (!res.ok) {
        setTeamError(payload?.error || "Unable to load teams.");
        return;
      }
      const items = Array.isArray(payload?.items) ? payload.items : [];
      setTeams(items);
      if (!selectedTeamId && items.length) {
        setSelectedTeamId(items[0].id);
      }
    } catch (error) {
      setTeamError((error as Error).message || "Unable to load teams.");
    } finally {
      setTeamLoading(false);
    }
  }

  async function createTeam() {
    if (!accessToken || !newTeamName.trim()) return;
    setTeamLoading(true);
    setTeamError("");
    try {
      const res = await apiFetch(
        "/api/v1/teams",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: newTeamName.trim(), seat_count: 3 }),
        },
        accessToken,
      );
      const payload = await res.json();
      if (!res.ok) {
        setTeamError(payload?.error || "Unable to create team.");
        return;
      }
      setNewTeamName("");
      await loadTeams();
      if (payload?.id) setSelectedTeamId(payload.id);
    } catch (error) {
      setTeamError((error as Error).message || "Unable to create team.");
    } finally {
      setTeamLoading(false);
    }
  }

  async function loadTeamMembers(teamId: string) {
    if (!accessToken || !teamId) return;
    try {
      const res = await apiFetch(`/api/v1/teams/${teamId}/members`, {}, accessToken);
      const payload = await res.json();
      if (!res.ok) {
        setTeamError(payload?.error || "Unable to load members.");
        return;
      }
      setTeamMembers(Array.isArray(payload?.items) ? payload.items : []);
    } catch (error) {
      setTeamError((error as Error).message || "Unable to load members.");
    }
  }

  async function addTeamMember() {
    if (!accessToken || !selectedTeamId || !memberEmail.trim()) return;
    try {
      const res = await apiFetch(
        `/api/v1/teams/${selectedTeamId}/members`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: memberEmail.trim(), role: "member" }),
        },
        accessToken,
      );
      const payload = await res.json();
      if (!res.ok) {
        setTeamError(payload?.error || "Unable to add member.");
        return;
      }
      setMemberEmail("");
      await loadTeamMembers(selectedTeamId);
    } catch (error) {
      setTeamError((error as Error).message || "Unable to add member.");
    }
  }

  async function loadApiKeys() {
    if (!accessToken) return;
    try {
      const res = await apiFetch("/api/v1/api-keys", {}, accessToken);
      const payload = await res.json();
      if (!res.ok) return;
      setApiKeys(Array.isArray(payload?.items) ? payload.items : []);
    } catch {
      // ignore
    }
  }

  async function createApiKey() {
    if (!accessToken || !apiKeyLabel.trim()) return;
    const body = {
      label: apiKeyLabel.trim(),
      team_id: selectedTeamId || undefined,
    };
    try {
      const res = await apiFetch(
        "/api/v1/api-keys",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
        accessToken,
      );
      const payload = await res.json();
      if (!res.ok) return;
      setApiKeyLabel("");
      setApiKeySecret(payload?.key || null);
      setIntegrationNotice(payload?.key ? "Copy the API key now. You will not see it again." : "");
      await loadApiKeys();
    } catch {
      // ignore
    }
  }

  async function loadWebhooks() {
    if (!accessToken) return;
    try {
      const res = await apiFetch("/api/v1/webhooks", {}, accessToken);
      const payload = await res.json();
      if (!res.ok) return;
      setWebhooks(Array.isArray(payload?.items) ? payload.items : []);
    } catch {
      // ignore
    }
  }

  async function createWebhook() {
    if (!accessToken || !webhookUrl.trim()) return;
    const events = webhookEvents
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!events.length) return;
    try {
      const res = await apiFetch(
        "/api/v1/webhooks",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: webhookUrl.trim(), events, team_id: selectedTeamId || undefined }),
        },
        accessToken,
      );
      const payload = await res.json();
      if (!res.ok) return;
      setWebhookUrl("");
      await loadWebhooks();
      if (payload?.secret) {
        setIntegrationNotice(`Webhook secret: ${payload.secret}`);
      }
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (!accessToken) return;
    loadTeams();
    loadApiKeys();
    loadWebhooks();
    refreshStudentStatus();
  }, [accessToken]);

  useEffect(() => {
    if (selectedTeamId) {
      loadTeamMembers(selectedTeamId);
    }
  }, [selectedTeamId]);

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
              <div className="text-xl font-semibold mt-2">Plans</div>
              <div className="mt-2 text-sm text-[var(--muted)]">
                Unlock longer videos, more exports, and higher monthly limits.
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-[var(--border)] p-4">
                  <div className="font-medium">Student</div>
                  <div className="text-xs text-[var(--muted)] mt-1">Longer videos and core exports.</div>
                  <button
                    type="button"
                    disabled={billingBusy}
                    onClick={() => startCheckout("student")}
                    className="mt-3 w-full rounded-xl bg-slate-900 text-white px-4 py-2 text-sm hover:bg-slate-800 transition disabled:opacity-60"
                  >
                    Upgrade to Student
                  </button>
                </div>
                <div className="rounded-xl border border-[var(--border)] p-4">
                  <div className="font-medium">Pro</div>
                  <div className="text-xs text-[var(--muted)] mt-1">Batch processing + advanced exports.</div>
                  <button
                    type="button"
                    disabled={billingBusy}
                    onClick={() => startCheckout("pro")}
                    className="mt-3 w-full rounded-xl bg-teal-600 text-white px-4 py-2 text-sm hover:bg-teal-600/90 transition disabled:opacity-60"
                  >
                    Upgrade to Pro
                  </button>
                </div>
                <div className="rounded-xl border border-[var(--border)] p-4">
                  <div className="font-medium">Team</div>
                  <div className="text-xs text-[var(--muted)] mt-1">Shared collections, admin tools, branded PDFs.</div>
                  <button
                    type="button"
                    disabled={billingBusy}
                    onClick={() => startCheckout("team")}
                    className="mt-3 w-full rounded-xl bg-indigo-600 text-white px-4 py-2 text-sm hover:bg-indigo-600/90 transition disabled:opacity-60"
                  >
                    Upgrade to Team
                  </button>
                </div>
              </div>
              <div className="mt-4">
                <button
                  type="button"
                  disabled={billingBusy}
                  onClick={openPortal}
                  className="rounded-xl border border-[var(--border)] px-4 py-2 text-sm hover:bg-white/10 transition disabled:opacity-60"
                >
                  Manage billing
                </button>
                <button
                  type="button"
                  disabled={studentBusy}
                  onClick={startStudentVerification}
                  className="ml-2 rounded-xl border border-[var(--border)] px-4 py-2 text-sm hover:bg-white/10 transition disabled:opacity-60"
                >
                  Verify student status
                </button>
              </div>
              <div className="mt-2 text-xs text-[var(--muted)]">
                Student verification: {studentStatus}{studentRef ? ` (${studentRef})` : ""}
              </div>
              {billingError && <div className="mt-3 text-xs text-red-500">{billingError}</div>}
            </div>

            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
              <div className="text-sm text-[var(--muted)]">Teams</div>
              <div className="text-xl font-semibold mt-2">Workspace</div>
              <div className="mt-3 flex gap-2 flex-wrap">
                <input
                  className="flex-1 min-w-[200px] rounded-xl border border-[var(--border)] px-3 py-2 text-sm bg-transparent"
                  placeholder="Team name"
                  value={newTeamName}
                  onChange={(event) => setNewTeamName(event.target.value)}
                />
                <button
                  type="button"
                  disabled={teamLoading}
                  onClick={createTeam}
                  className="rounded-xl bg-slate-900 text-white px-4 py-2 text-sm hover:bg-slate-800 transition disabled:opacity-60"
                >
                  Create team
                </button>
              </div>
              {teamError && <div className="mt-3 text-xs text-red-500">{teamError}</div>}
              <div className="mt-4 grid gap-2">
                {teams.map((team) => (
                  <button
                    key={team.id}
                    type="button"
                    className={`rounded-xl border px-3 py-2 text-left text-sm transition ${
                      selectedTeamId === team.id
                        ? "border-teal-500 bg-teal-500/10"
                        : "border-[var(--border)] hover:bg-white/5"
                    }`}
                    onClick={() => setSelectedTeamId(team.id)}
                  >
                    <div className="font-medium">{team.name}</div>
                    <div className="text-xs text-[var(--muted)]">Plan: {team.plan}</div>
                  </button>
                ))}
                {!teams.length && <div className="text-xs text-[var(--muted)]">No teams yet.</div>}
              </div>
              <div className="mt-4">
                <div className="text-sm font-medium">Members</div>
                <div className="mt-2 flex gap-2 flex-wrap">
                  <input
                    className="flex-1 min-w-[200px] rounded-xl border border-[var(--border)] px-3 py-2 text-sm bg-transparent"
                    placeholder="Invite by email"
                    value={memberEmail}
                    onChange={(event) => setMemberEmail(event.target.value)}
                  />
                  <button
                    type="button"
                    onClick={addTeamMember}
                    className="rounded-xl border border-[var(--border)] px-4 py-2 text-sm hover:bg-white/10 transition"
                  >
                    Add member
                  </button>
                </div>
                <div className="mt-3 grid gap-2">
                  {teamMembers.map((member) => (
                    <div key={member.id} className="rounded-xl border border-[var(--border)] px-3 py-2 text-sm">
                      <div className="font-medium">{member.email}</div>
                      <div className="text-xs text-[var(--muted)]">{member.role} · {member.status}</div>
                    </div>
                  ))}
                  {!teamMembers.length && <div className="text-xs text-[var(--muted)]">No members yet.</div>}
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
              <div className="text-sm text-[var(--muted)]">API Keys</div>
              <div className="text-xl font-semibold mt-2">Developer access</div>
              <div className="mt-3 flex gap-2 flex-wrap">
                <input
                  className="flex-1 min-w-[200px] rounded-xl border border-[var(--border)] px-3 py-2 text-sm bg-transparent"
                  placeholder="Key label"
                  value={apiKeyLabel}
                  onChange={(event) => setApiKeyLabel(event.target.value)}
                />
                <button
                  type="button"
                  onClick={createApiKey}
                  className="rounded-xl bg-slate-900 text-white px-4 py-2 text-sm hover:bg-slate-800 transition"
                >
                  Create key
                </button>
              </div>
              {apiKeySecret && (
                <div className="mt-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
                  Copy this key now: <span className="font-mono">{apiKeySecret}</span>
                </div>
              )}
              {integrationNotice && (
                <div className="mt-3 text-xs text-amber-400">{integrationNotice}</div>
              )}
              <div className="mt-3 grid gap-2">
                {apiKeys.map((key) => (
                  <div key={key.id} className="rounded-xl border border-[var(--border)] px-3 py-2 text-sm">
                    <div className="font-medium">{key.label}</div>
                    <div className="text-xs text-[var(--muted)]">Prefix: {key.key_prefix}</div>
                  </div>
                ))}
                {!apiKeys.length && <div className="text-xs text-[var(--muted)]">No API keys yet.</div>}
              </div>
            </div>

            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
              <div className="text-sm text-[var(--muted)]">Webhooks</div>
              <div className="text-xl font-semibold mt-2">Event delivery</div>
              <div className="mt-3 grid gap-2">
                <input
                  className="rounded-xl border border-[var(--border)] px-3 py-2 text-sm bg-transparent"
                  placeholder="https://example.com/webhook"
                  value={webhookUrl}
                  onChange={(event) => setWebhookUrl(event.target.value)}
                />
                <input
                  className="rounded-xl border border-[var(--border)] px-3 py-2 text-sm bg-transparent"
                  placeholder="event1, event2"
                  value={webhookEvents}
                  onChange={(event) => setWebhookEvents(event.target.value)}
                />
                <button
                  type="button"
                  onClick={createWebhook}
                  className="rounded-xl border border-[var(--border)] px-4 py-2 text-sm hover:bg-white/10 transition"
                >
                  Add webhook
                </button>
              </div>
              <div className="mt-3 grid gap-2">
                {webhooks.map((hook) => (
                  <div key={hook.id} className="rounded-xl border border-[var(--border)] px-3 py-2 text-sm">
                    <div className="font-medium">{hook.url}</div>
                    <div className="text-xs text-[var(--muted)]">Events: {hook.events.join(", ")}</div>
                  </div>
                ))}
                {!webhooks.length && <div className="text-xs text-[var(--muted)]">No webhooks yet.</div>}
              </div>
            </div>
          </div>
        </AuthGuard>
      </main>
    </div>
  );
}
