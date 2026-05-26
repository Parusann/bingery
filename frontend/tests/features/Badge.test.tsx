import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/features/schedule/Badge";

describe("Badge", () => {
  it("renders SUB label and peach text class for sub", () => {
    render(<Badge type="sub" />);
    const el = screen.getByText("SUB");
    expect(el).toBeInTheDocument();
    expect(el.className).toMatch(/text-peach/);
  });

  it("renders DUB label and sage text class for dub", () => {
    render(<Badge type="dub" />);
    const el = screen.getByText("DUB");
    expect(el).toBeInTheDocument();
    expect(el.className).toMatch(/text-sage/);
  });
});
