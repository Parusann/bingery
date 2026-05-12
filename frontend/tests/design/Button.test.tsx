import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/design/Button";

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Tap me</Button>);
    expect(screen.getByRole("button", { name: "Tap me" })).toBeInTheDocument();
  });

  it("fires onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("disables when loading", () => {
    render(<Button loading>Send</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("applies variant class", () => {
    const { rerender } = render(<Button variant="primary">P</Button>);
    expect(screen.getByRole("button").className).toMatch(/amber/);
    rerender(<Button variant="ghost">G</Button>);
    expect(screen.getByRole("button").className).toMatch(/ghost|transparent|border/);
  });
});
