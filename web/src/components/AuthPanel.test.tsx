import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuthPanelView } from "./AuthPanel";

describe("AuthPanelView", () => {
  it("renders guest controls", () => {
    render(
      <AuthPanelView
        status="guest"
        onGoogle={vi.fn()}
        onEmailSignIn={vi.fn()}
        onEmailSignUp={vi.fn()}
        onSignOut={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /continue with google/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create account/i })).toBeInTheDocument();
  });

  it("renders authenticated state", () => {
    render(
      <AuthPanelView
        status="authed"
        email="user@example.com"
        onGoogle={vi.fn()}
        onEmailSignIn={vi.fn()}
        onEmailSignUp={vi.fn()}
        onSignOut={vi.fn()}
      />,
    );

    expect(screen.getByText(/signed in as/i)).toBeInTheDocument();
    expect(screen.getByText(/user@example.com/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });
});
