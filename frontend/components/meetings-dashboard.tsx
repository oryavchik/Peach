"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { CalendarDays, Clock, Users } from "lucide-react";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type MeetingInput } from "@/lib/api";

export function MeetingsDashboard() {
  const queryClient = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [formError, setFormError] = useState("");
  const meetings = useQuery({
    queryKey: ["meetings", offset],
    queryFn: () => api.listMeetings(offset),
  });
  const stats = useQuery({
    queryKey: ["meeting-stats"],
    queryFn: api.meetingStats,
  });
  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["meetings"] }),
      queryClient.invalidateQueries({ queryKey: ["meeting-stats"] }),
    ]);
  }
  const report = useMutation({ mutationFn: api.requestMeetingReport });
  const create = useMutation({
    mutationFn: api.createMeeting,
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: api.deleteMeeting,
    onSuccess: async () => {
      if (meetings.data?.items.length === 1 && offset > 0)
        setOffset(offset - 20);
      await refresh();
    },
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const start = new Date(`${values.get("date")}T${values.get("start")}`);
    const end = new Date(`${values.get("date")}T${values.get("end")}`);
    const minutes = (end.getTime() - start.getTime()) / 60000;
    const title = String(values.get("title")).trim();
    if (!title || !Number.isFinite(minutes) || minutes <= 0) {
      setFormError(
        "Enter a title and an end time after the start time on the same day.",
      );
      return;
    }
    setFormError("");
    const payload: MeetingInput = {
      title,
      starts_at: start.toISOString(),
      duration_minutes: minutes,
      participant_count: Number(values.get("participants")),
    };
    try {
      await create.mutateAsync(payload);
      form.reset();
    } catch {
      /* The mutation error is shown below the form. */
    }
  }

  const data = stats.data;
  const difference = data
    ? data.meeting_count - data.previous_meeting_count
    : 0;
  const error = meetings.error || stats.error;

  return (
    <div className="mx-auto grid w-full max-w-5xl gap-8 px-6 py-10 sm:px-8">
      <PageHeader
        icon="📅"
        title="Meetings"
        description="Make room for better conversations. Plan your meetings and keep track of your week."
        action={
          <Button disabled={report.isPending} onClick={() => report.mutate()}>
            {report.isPending
              ? "Requesting report…"
              : "Send me this week's report"}
          </Button>
        }
      />
      {report.isSuccess && (
        <p role="status" className="text-sm text-muted-foreground">
          Report requested for {report.data.week}. Your personal CSV will be
          emailed to your verified account address.
        </p>
      )}
      {report.error && (
        <p role="alert" className="text-sm text-destructive">
          {report.error.message}
        </p>
      )}
      {error && (
        <div
          role="alert"
          className="rounded-xl border border-destructive p-4 text-sm"
        >
          {error.message}{" "}
          <Button
            variant="outline"
            onClick={() => {
              void meetings.refetch();
              void stats.refetch();
            }}
          >
            Retry
          </Button>
        </div>
      )}
      <section
        aria-label="Weekly statistics"
        className="grid gap-4 sm:grid-cols-3"
      >
        {[
          {
            label: "Meetings this week",
            value: data?.meeting_count,
            icon: CalendarDays,
          },
          {
            label: "Total meeting hours",
            value: data?.total_hours,
            icon: Clock,
          },
          {
            label: "Meetings vs. last week",
            value: data
              ? `${difference > 0 ? "+" : ""}${difference}`
              : undefined,
            icon: Users,
          },
        ].map(({ label, value, icon: Icon }) => (
          <div key={label} className="rounded-xl border bg-card p-5 shadow-sm">
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              {label}
              <Icon className="size-4" />
            </div>
            <p className="mt-4 text-3xl font-semibold" aria-live="polite">
              {value ?? "—"}
            </p>
          </div>
        ))}
      </section>
      <p className="-mt-5 text-xs text-muted-foreground">
        Weeks run Monday–Sunday in UTC, matching weekly reports. Meeting times
        use your local timezone.
        {data &&
          ` Last week: ${data.previous_meeting_count} meetings · ${data.previous_total_hours} hours.`}
      </p>
      <section
        className="rounded-xl border bg-card p-6 shadow-sm"
        aria-labelledby="create-meeting"
      >
        <h2 id="create-meeting" className="mb-5 text-lg font-semibold">
          Create a meeting
        </h2>
        <form
          onSubmit={submit}
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <div className="grid gap-2 sm:col-span-2 lg:col-span-3">
            <Label htmlFor="meeting-title">Title</Label>
            <Input
              id="meeting-title"
              name="title"
              placeholder="e.g. Weekly team sync"
              required
              maxLength={200}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="meeting-date">Date</Label>
            <Input id="meeting-date" name="date" type="date" required />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="meeting-start">Start time</Label>
            <Input id="meeting-start" name="start" type="time" required />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="meeting-end">End time</Label>
            <Input id="meeting-end" name="end" type="time" required />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="meeting-participants">Participants</Label>
            <Input
              id="meeting-participants"
              name="participants"
              type="number"
              min={1}
              max={2147483647}
              defaultValue={1}
              required
            />
          </div>
          <div className="flex items-end">
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create meeting"}
            </Button>
          </div>
          {(formError || create.error) && (
            <p
              role="alert"
              className="text-sm text-destructive sm:col-span-2 lg:col-span-3"
            >
              {formError || create.error?.message}
            </p>
          )}
        </form>
      </section>
      <section
        aria-labelledby="all-meetings"
        className="overflow-hidden rounded-xl border bg-card shadow-sm"
      >
        <h2
          id="all-meetings"
          className="border-b px-6 py-5 text-lg font-semibold"
        >
          All meetings{" "}
          {meetings.data && (
            <span className="text-muted-foreground">
              ({meetings.data.total})
            </span>
          )}
        </h2>
        {meetings.isPending && (
          <p role="status" className="p-6 text-muted-foreground">
            Loading meetings…
          </p>
        )}
        {meetings.data?.total === 0 && (
          <p className="p-10 text-center text-muted-foreground">
            No meetings yet. Create your first meeting above.
          </p>
        )}
        {!!meetings.data?.items.length && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/40 text-muted-foreground">
                <tr>
                  {[
                    "Title",
                    "Date & time",
                    "Duration",
                    "Participants",
                    "Actions",
                  ].map((label) => (
                    <th key={label} className="px-6 py-3 font-medium">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {meetings.data.items.map((meeting) => (
                  <tr key={meeting.id} className="border-t">
                    <td className="max-w-64 break-words px-6 py-4 font-medium">
                      {meeting.title}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      {new Date(meeting.starts_at).toLocaleString([], {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                      <span className="block text-xs text-muted-foreground">
                        Ends{" "}
                        {new Date(
                          new Date(meeting.starts_at).getTime() +
                            meeting.duration_minutes * 60000,
                        ).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      {meeting.duration_minutes} min
                    </td>
                    <td className="px-6 py-4">{meeting.participant_count}</td>
                    <td className="px-6 py-4">
                      <Link
                        className="mr-3 inline-block underline"
                        href={`/meetings/agenda?meeting=${meeting.id}`}
                      >
                        Agenda
                      </Link>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={remove.isPending}
                        aria-label={`Delete ${meeting.title}`}
                        onClick={() => {
                          if (window.confirm(`Delete “${meeting.title}”?`))
                            remove.mutate(meeting.id);
                        }}
                      >
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {remove.error && (
          <p role="alert" className="px-6 py-3 text-sm text-destructive">
            {remove.error.message}
          </p>
        )}
        {meetings.data && meetings.data.total > 20 && (
          <div className="flex items-center justify-between border-t p-4">
            <Button
              variant="outline"
              disabled={offset === 0 || meetings.isFetching}
              onClick={() => setOffset(offset - 20)}
            >
              Previous
            </Button>
            <span className="text-sm">Page {offset / 20 + 1}</span>
            <Button
              variant="outline"
              disabled={
                offset + 20 >= meetings.data.total || meetings.isFetching
              }
              onClick={() => setOffset(offset + 20)}
            >
              Next
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
