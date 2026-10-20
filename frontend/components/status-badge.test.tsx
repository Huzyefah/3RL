import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./status-badge";

describe("StatusBadge", () => {
  it("renders an icon and text", () => {
    render(<StatusBadge />);
    const badge = screen.getByTestId("status-badge");
    expect(badge).toHaveTextContent("OK");
    expect(badge).toHaveTextContent("●");
  });
});
