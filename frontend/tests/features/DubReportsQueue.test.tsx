import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const useDubReportsMock = vi.hoisted(() => vi.fn());
const useUpdateDubReportMock = vi.hoisted(() => vi.fn());
const updateMutateMock = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/useDubReports", () => ({
  useDubReports: useDubReportsMock,
  useUpdateDubReport: useUpdateDubReportMock,
  useCreateDubReport: vi.fn(),
}));

import { DubReportsQueue } from "@/features/admin/DubReportsQueue";
import { useAuth } from "@/stores/auth";

const adminUser = {
  id: 1,
  email: "admin@example.com",
  username: "admin",
  display_name: null,
  avatar_url: null,
  bio: null,
  created_at: "2026-01-01",
};

const regularUser = {
  ...adminUser,
  id: 99,
  username: "regular",
  email: "regular@example.com",
};

beforeEach(() => {
  useDubReportsMock.mockReset();
  useUpdateDubReportMock.mockReset();
  updateMutateMock.mockReset();
  useUpdateDubReportMock.mockReturnValue({
    mutate: updateMutateMock,
    isPending: false,
  });
  useAuth.setState({ user: adminUser, status: "authenticated" });
});

describe("DubReportsQueue", () => {
  it("requires authentication", () => {
    useAuth.setState({ user: null, status: "idle" });
    useDubReportsMock.mockReturnValue({ isLoading: false, data: undefined });
    render(<DubReportsQueue />);
    expect(screen.getByText(/sign in required/i)).toBeInTheDocument();
  });

  it("rejects non-admin users", () => {
    useAuth.setState({ user: regularUser, status: "authenticated" });
    useDubReportsMock.mockReturnValue({ isLoading: false, data: undefined });
    render(<DubReportsQueue />);
    expect(screen.getByText(/admins only/i)).toBeInTheDocument();
  });

  it("renders skeleton blocks while loading", () => {
    useDubReportsMock.mockReturnValue({ isLoading: true, data: undefined });
    const { container } = render(<DubReportsQueue />);
    expect(container.querySelectorAll(".h-24")).toHaveLength(4);
  });

  it("renders empty-state message when the status bucket is empty", () => {
    useDubReportsMock.mockReturnValue({
      isLoading: false,
      data: { reports: [] },
    });
    render(<DubReportsQueue />);
    expect(screen.getByText(/no pending reports/i)).toBeInTheDocument();
  });

  it("renders rows with accept and reject buttons for pending reports", () => {
    useDubReportsMock.mockReturnValue({
      isLoading: false,
      data: {
        reports: [
          {
            id: 5,
            episode_id: 22,
            submitted_by: 12,
            air_date: "2026-06-01T12:00:00Z",
            status: "pending",
            note: "from the trailer",
            created_at: "2026-05-14T00:00:00Z",
            reviewed_at: null,
            reviewed_by: null,
          },
        ],
      },
    });
    render(<DubReportsQueue />);
    expect(screen.getByText(/episode #22/i)).toBeInTheDocument();
    expect(screen.getByText(/by user #12/i)).toBeInTheDocument();
    expect(screen.getByText(/from the trailer/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Accept$/ })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Reject$/ })
    ).toBeInTheDocument();
  });

  it("triggers the update mutation when Accept is clicked", () => {
    useDubReportsMock.mockReturnValue({
      isLoading: false,
      data: {
        reports: [
          {
            id: 7,
            episode_id: 30,
            submitted_by: 4,
            air_date: "2026-06-01T12:00:00Z",
            status: "pending",
            note: null,
            created_at: "2026-05-14T00:00:00Z",
            reviewed_at: null,
            reviewed_by: null,
          },
        ],
      },
    });
    render(<DubReportsQueue />);
    fireEvent.click(screen.getByRole("button", { name: /^Accept$/ }));
    expect(updateMutateMock).toHaveBeenCalledWith({
      id: 7,
      body: { status: "accepted" },
    });
  });

  it("does not render moderation buttons for accepted reports", () => {
    useDubReportsMock.mockReturnValue({
      isLoading: false,
      data: {
        reports: [
          {
            id: 9,
            episode_id: 1,
            submitted_by: 2,
            air_date: "2026-06-01T12:00:00Z",
            status: "accepted",
            note: null,
            created_at: "2026-05-14T00:00:00Z",
            reviewed_at: "2026-05-15T00:00:00Z",
            reviewed_by: 1,
          },
        ],
      },
    });
    render(<DubReportsQueue />);
    expect(screen.queryByRole("button", { name: /^Accept$/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Reject$/ })).toBeNull();
  });
});
