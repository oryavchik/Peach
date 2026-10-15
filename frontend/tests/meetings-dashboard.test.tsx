import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MeetingsDashboard } from "@/components/meetings-dashboard";
import { api, type Meeting } from "@/lib/api";
import { renderWithQuery } from "./utils";

const meeting: Meeting = {
  id: "meeting-1",
  title: "Team sync",
  starts_at: "2026-10-15T10:00:00Z",
  duration_minutes: 60,
  participant_count: 3,
  created_at: "2026-10-15T08:00:00Z",
};
function mockData(items = [meeting]) {
  vi.spyOn(api, "listMeetings").mockResolvedValue({
    items,
    total: items.length,
  });
  vi.spyOn(api, "meetingStats").mockResolvedValue({
    week_start: "2026-10-12T00:00:00Z",
    week_end: "2026-10-19T00:00:00Z",
    meeting_count: 1,
    total_hours: 1,
    previous_meeting_count: 2,
    previous_total_hours: 3,
  });
}
function fillTimes(end = "11:00") {
  fireEvent.change(screen.getByLabelText("Title"), {
    target: { value: "New sync" },
  });
  fireEvent.change(screen.getByLabelText("Date"), {
    target: { value: "2026-10-15" },
  });
  fireEvent.change(screen.getByLabelText("Start time"), {
    target: { value: "10:00" },
  });
  fireEvent.change(screen.getByLabelText("End time"), {
    target: { value: end },
  });
}

describe("MeetingsDashboard", () => {
  it("shows persisted meetings and previous week comparison", async () => {
    mockData();
    renderWithQuery(<MeetingsDashboard />);
    expect(await screen.findByText("Team sync")).toBeInTheDocument();
    expect(screen.getByText("-1")).toBeInTheDocument();
    expect(screen.getByText("60 min")).toBeInTheDocument();
  });
  it("creates a meeting using a UTC timestamp and duration", async () => {
    mockData([]);
    const create = vi.spyOn(api, "createMeeting").mockResolvedValue(meeting);
    renderWithQuery(<MeetingsDashboard />);
    fillTimes();
    await userEvent.click(
      screen.getByRole("button", { name: "Create meeting" }),
    );
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(
        {
          title: "New sync",
          starts_at: new Date("2026-10-15T10:00").toISOString(),
          duration_minutes: 60,
          participant_count: 1,
        },
        expect.anything(),
      ),
    );
    await waitFor(() => expect(screen.getByLabelText("Title")).toHaveValue(""));
  });
  it("rejects an end time before the start time", async () => {
    mockData([]);
    const create = vi.spyOn(api, "createMeeting");
    renderWithQuery(<MeetingsDashboard />);
    fillTimes("09:00");
    await userEvent.click(
      screen.getByRole("button", { name: "Create meeting" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "end time after",
    );
    expect(create).not.toHaveBeenCalled();
  });
  it("deletes after confirmation and refreshes the list", async () => {
    mockData();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const remove = vi.spyOn(api, "deleteMeeting").mockResolvedValue(undefined);
    renderWithQuery(<MeetingsDashboard />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Delete Team sync" }),
    );
    await waitFor(() =>
      expect(remove).toHaveBeenCalledWith("meeting-1", expect.anything()),
    );
    await waitFor(() => expect(api.listMeetings).toHaveBeenCalledTimes(2));
  });
  it("shows load errors and retries", async () => {
    mockData([]);
    vi.mocked(api.listMeetings).mockRejectedValueOnce(
      new Error("Could not reach the API"),
    );
    renderWithQuery(<MeetingsDashboard />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not reach the API",
    );
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/No meetings yet/)).toBeInTheDocument();
  });
});
