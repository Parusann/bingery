import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FilterPills } from "@/features/schedule/FilterPills";

describe("FilterPills", () => {
  it("renders all three lang options and the mine toggle", () => {
    render(
      <FilterPills
        lang="both"
        myShowsOnly={false}
        onLangChange={() => {}}
        onMineToggle={() => {}}
      />,
    );
    ["SUB", "DUB", "BOTH"].forEach((l) =>
      expect(screen.getByText(l)).toBeInTheDocument(),
    );
    expect(screen.getByText(/my shows/i)).toBeInTheDocument();
  });

  it("calls onLangChange with the selected option", () => {
    const onLangChange = vi.fn();
    render(
      <FilterPills
        lang="both"
        myShowsOnly={false}
        onLangChange={onLangChange}
        onMineToggle={() => {}}
      />,
    );
    fireEvent.click(screen.getByText("DUB"));
    expect(onLangChange).toHaveBeenCalledWith("dub");
  });

  it("calls onMineToggle on click", () => {
    const onMineToggle = vi.fn();
    render(
      <FilterPills
        lang="both"
        myShowsOnly={false}
        onLangChange={() => {}}
        onMineToggle={onMineToggle}
      />,
    );
    fireEvent.click(screen.getByText(/my shows/i));
    expect(onMineToggle).toHaveBeenCalled();
  });

  it("marks the active lang with data-active=true", () => {
    const { container } = render(
      <FilterPills
        lang="sub"
        myShowsOnly={false}
        onLangChange={() => {}}
        onMineToggle={() => {}}
      />,
    );
    const active = container.querySelector('[data-active="true"]');
    expect(active?.textContent).toBe("SUB");
  });
});
