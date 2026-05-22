import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AuthGuard } from "./AuthGuard";
import { AuthContext, type AuthContextValue } from "@/hooks/useAuth";

describe("AuthGuard", () => {
  it("shows guest prompt when unauthenticated", () => {
    const value: AuthContextValue = {
      status: "guest",
      user: null,
      session: null,
      accessToken: "",
      isConfigured: true,
      signInWithGoogle: async () => ({}) as any,
      signInWithPassword: async () => ({}) as any,
      signUpWithPassword: async () => ({}) as any,
      signOut: async () => ({}),
    };

    render(
      <AuthContext.Provider value={value}>
        <AuthGuard>Protected content</AuthGuard>
      </AuthContext.Provider>,
    );

    expect(screen.getAllByText(/guest mode/i).length).toBeGreaterThan(0);
    expect(screen.queryByText("Protected content")).toBeNull();
  });

  it("renders children when authenticated", () => {
    const value: AuthContextValue = {
      status: "authed",
      user: { email: "user@example.com" } as any,
      session: {} as any,
      accessToken: "token",
      isConfigured: true,
      signInWithGoogle: async () => ({}) as any,
      signInWithPassword: async () => ({}) as any,
      signUpWithPassword: async () => ({}) as any,
      signOut: async () => ({}),
    };

    render(
      <AuthContext.Provider value={value}>
        <AuthGuard>Protected content</AuthGuard>
      </AuthContext.Provider>,
    );

    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });
});
