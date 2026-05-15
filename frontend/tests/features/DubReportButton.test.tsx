import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const useAnimeEpisodesMock = vi.hoisted(() => vi.fn());
const useScheduleMock = vi.hoisted(() => vi.fn());
const createDubReportMock = vi.hoisted(() => vi.fn());
const useCreateDubReportMock = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/useSchedule", () => ({
  useSchedule: useScheduleMock,
  useAnimeEpisodes: useAnimeEpisodesMock,
}));

vi.mock("@/hooks/useDubReports", () => ({
  useCreateDubReport: useCreateDubReportMock,
  useDubReports: vi.fn(),
  useUpdateDubReport: vi.fn(),
}));

import { DubReportButton } from "@/features/details/DubReportButton";
import { useAuth } from "@/stores/auth";

const fakeUser = {
  id: 7,
  email: "u@example.com",
  username: "tester",
  display_name: null,
  avatar_url: null,
  bio: null,
  created_at: "2026-01-01",
};

const sampleEpisodes = [
  { id: 11, episode_number: 1, air_date_sub: null, air_date_dub: null },
  { id: 12, episode_number: 2, air_date_sub: null, air_date_dub: null },
];

beforeEach(() => {
  useAnimeEpisodesMock.mockReset();
  useCreateDubReportMock.mockReset();
  createDubReportMock.mockReset();
  useCreateDubReportMock.mockReturnValue({
    mutateAsync: createDubReportMock,
    isPending: false,
  });
  useAnimeEpisodesMock.mockReturnValue({
    data: { episodes: sampleEpisodes, next_sub: null, next_dub: null },
    isLoading: false,
  });
  useAuth.setState({ user: fakeUser, status: "authenticated" });
});

describe("DubReportButton", () => {
  it("renders nothing when no user is signed in", () => {
    useAuth.setState({ user: null, status: "idle" });
    const { container } = render(<DubReportButton animeId={42} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the trigger button when user is signed in", () => {
    render(<DubReportButton animeId={42} />);
    expect(
      screen.getByRole("button", { name: /report missing dub date/i })
    ).toBeInTheDocument();
  });

  it("opens the modal with the form when the trigger is clicked", () => {
    render(<DubReportButton animeId={42} />);
    fireEvent.click(
      screen.getByRole("button", { name: /report missing dub date/i })
    );
    expect(
      screen.getByRole("heading", { name: /report a dub air date/i })
    ).toBeInTheDocument();
    // Episode select populated from mocked hook.
    expect(screen.getByText("Episode 1")).toBeInTheDocument();
    expect(screen.getByText("Episode 2")).toBeInTheDocument();
  });

  it("submits the form payload through the createDubReport mutation", async () => {
    createDubReportMock.mockResolvedValue({});
    render(<DubReportButton animeId={42} />);
    fireEvent.click(
      screen.getByRole("button", { name: /report missing dub date/i })
    );

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "12" },
    });
    // datetime-local has no role; query by display value.
    const dateInput = screen
      .getByText(/Dub air date and time/i)
      .parentElement?.querySelector('input[type="datetime-local"]') as HTMLInputElement;
    fireEvent.change(dateInput, { target: { value: "2026-06-01T12:00" } });

    fireEvent.click(screen.getByRole("button", { name: /^submit$/i }));

    // Wait a microtask for the mutateAsync promise.
    await Promise.resolve();
    expect(createDubReportMock).toHaveBeenCalledTimes(1);
    const arg = createDubReportMock.mock.calls[0][0];
    expect(arg.episode_id).toBe(12);
    expect(arg.air_date).toBe("2026-06-01T12:00:00Z");
  });

  it("shows an error when submitted without an episode picked", () => {
    render(<DubReportButton animeId={42} />);
    fireEvent.click(
      screen.getByRole("button", { name: /report missing dub date/i })
    );
    // Bypass native HTML validation by directly submitting via the form.
    const submit = screen.getByRole("button", { name: /^submit$/i });
    const form = submit.closest("form");
    if (!form) throw new Error("form not found");
    fireEvent.submit(form);
    expect(screen.getByRole("alert")).toHaveTextContent(/pick an episode/i);
    expect(createDubReportMock).not.toHaveBeenCalled();
  });
});
