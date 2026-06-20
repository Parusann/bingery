import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EstimatedTag } from "@/features/schedule/EstimatedTag";

describe("EstimatedTag", () => {
  it("renders 'estimated' label", () => {
    render(<EstimatedTag />);
    expect(screen.getByText(/estimated/i)).toBeInTheDocument();
  });

  it("exposes a placeholder tooltip via title attribute", () => {
    render(<EstimatedTag />);
    const el = screen.getByText(/estimated/i).closest("span");
    expect(el?.getAttribute("title") ?? "").toMatch(/placeholder/i);
  });
});
