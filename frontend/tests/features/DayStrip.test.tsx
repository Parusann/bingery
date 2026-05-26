import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DayStrip } from "@/features/schedule/DayStrip";

const dates = [
  "2026-05-24", "2026-05-25", "2026-05-26", "2026-05-27",
  "2026-05-28", "2026-05-29", "2026-05-30",
];

describe("DayStrip", () => {
  it("renders 7 chips with weekday labels", () => {
    const noop = () => {};
    render(
      <DayStrip
        weekStart="2026-05-24"
        todayIso="2026-05-26"
        episodeCounts={{ "2026-05-24": 3 }}
        onChipClick={noop}
        onPrevWeek={noop}
        onNextWeek={noop}
      />,
    );
    ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"].forEach((d) =>
      expect(screen.getByText(d)).toBeInTheDocument(),
    );
    dates.forEach((d) => {
      const dayNum = Number(d.split("-")[2]);
      expect(screen.getAllByText(String(dayNum)).length).toBeGreaterThan(0);
    });
  });

  it("highlights today's chip with data-today=true", () => {
    const noop = () => {};
    const { container } = render(
      <DayStrip
        weekStart="2026-05-24"
        todayIso="2026-05-26"
        episodeCounts={{}}
        onChipClick={noop}
        onPrevWeek={noop}
        onNextWeek={noop}
      />,
    );
    const today = container.querySelector('[data-today="true"]');
    expect(today).not.toBeNull();
    expect(today?.textContent).toContain("26");
  });

  it("fires onChipClick with the clicked date", () => {
    const onChipClick = vi.fn();
    render(
      <DayStrip
        weekStart="2026-05-24"
        todayIso="2026-05-26"
        episodeCounts={{}}
        onChipClick={onChipClick}
        onPrevWeek={() => {}}
        onNextWeek={() => {}}
      />,
    );
    fireEvent.click(screen.getByText("27"));
    expect(onChipClick).toHaveBeenCalledWith("2026-05-27");
  });

  it("fires prev/next week handlers from chevrons", () => {
    const onPrevWeek = vi.fn();
    const onNextWeek = vi.fn();
    render(
      <DayStrip
        weekStart="2026-05-24"
        todayIso="2026-05-26"
        episodeCounts={{}}
        onChipClick={() => {}}
        onPrevWeek={onPrevWeek}
        onNextWeek={onNextWeek}
      />,
    );
    fireEvent.click(screen.getByLabelText(/previous week/i));
    fireEvent.click(screen.getByLabelText(/next week/i));
    expect(onPrevWeek).toHaveBeenCalled();
    expect(onNextWeek).toHaveBeenCalled();
  });
});
