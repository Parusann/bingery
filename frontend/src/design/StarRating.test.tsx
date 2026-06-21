// @vitest-environment jsdom
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StarRating } from "./StarRating";

describe("StarRating", () => {
  it("renders 10 rating buttons", () => {
    render(<StarRating value={0} onChange={() => {}} />);
    expect(screen.getAllByRole("button")).toHaveLength(10);
  });

  it("reports the clicked star's value", async () => {
    const onChange = vi.fn();
    render(<StarRating value={0} onChange={onChange} />);
    await userEvent.click(screen.getByLabelText("Rate 7 of 10"));
    expect(onChange).toHaveBeenCalledWith(7);
  });
});
