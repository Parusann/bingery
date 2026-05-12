import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StarRating } from "@/design/StarRating";

describe("StarRating", () => {
  it("renders 10 slots", () => {
    render(<StarRating value={0} onChange={() => {}} />);
    expect(screen.getAllByRole("button")).toHaveLength(10);
  });

  it("shows current value", () => {
    render(<StarRating value={7} onChange={() => {}} />);
    expect(screen.getByLabelText("Rating 7 of 10")).toBeInTheDocument();
  });

  it("fires onChange on click", async () => {
    const onChange = vi.fn();
    render(<StarRating value={0} onChange={onChange} />);
    await userEvent.click(screen.getAllByRole("button")[4]);
    expect(onChange).toHaveBeenCalledWith(5);
  });

  it("ignores clicks in readOnly mode", async () => {
    const onChange = vi.fn();
    render(<StarRating value={3} onChange={onChange} readOnly />);
    await userEvent.click(screen.getAllByRole("button")[0]);
    expect(onChange).not.toHaveBeenCalled();
  });
});
