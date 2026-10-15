"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { agendaApi, type Agenda, type AISuggestion } from "@/lib/api";

const empty = (): Agenda => ({
  title: null,
  starts_at: null,
  duration_minutes: null,
  items: [],
  action_items: [],
  language: "en",
});

export function AgendaEditor() {
  const aiEnabled = process.env.NEXT_PUBLIC_AGENDA_PARSER_ENABLED === "true";
  const id = useSearchParams().get("meeting") ?? "";
  const queryClient = useQueryClient();
  const meeting = useQuery({
    queryKey: ["agenda", id],
    queryFn: () => agendaApi.get(id),
    enabled: !!id,
  });
  const [draft, setDraft] = useState<Agenda | null>(null);
  const [suggestion, setSuggestion] = useState<AISuggestion | null>(null);
  const [marked, setMarked] = useState<Set<string>>(new Set());
  const [text, setText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const agenda = draft ?? meeting.data?.agenda ?? empty();
  const original =
    draft === null ? (meeting.data?.ai_suggestion ?? null) : suggestion;

  function touch(path: string) {
    setMarked((previous) => {
      const next = new Set(previous);
      next.delete(path);
      return next;
    });
    setSaved(false);
  }
  function update(next: Agenda, path: string) {
    if (draft === null) setSuggestion(meeting.data?.ai_suggestion ?? null);
    setDraft(next);
    touch(path);
  }
  function removeRow(collection: "items" | "action_items", index: number) {
    update(
      {
        ...agenda,
        [collection]: agenda[collection].filter((_, n) => n !== index),
      },
      collection,
    );
    setMarked((previous) => {
      const next = new Set<string>();
      for (const path of previous) {
        const [group, row, field] = path.split(".");
        if (group !== collection) next.add(path);
        else if (Number(row) !== index)
          next.add(
            `${group}.${Number(row) > index ? Number(row) - 1 : row}.${field}`,
          );
      }
      return next;
    });
  }
  function badge(path: string) {
    return marked.has(path) ? (
      <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-900">
        suggested
      </span>
    ) : null;
  }
  async function parse() {
    if (!aiEnabled) return;
    if (text.length > 10000) {
      setError("Text must be no longer than 10,000 characters.");
      return;
    }
    const active = new AbortController();
    controller.current = active;
    setParsing(true);
    setError("");
    setSaved(false);
    try {
      const result = await agendaApi.parse(text, active.signal);
      if (active.signal.aborted) return;
      setDraft(structuredClone(result.agenda));
      setSuggestion(result);
      const paths = new Set<string>();
      for (const key of [
        "title",
        "starts_at",
        "duration_minutes",
        "language",
      ] as const)
        if (result.agenda[key] !== null) paths.add(key);
      result.agenda.items.forEach((row, i) =>
        Object.entries(row).forEach(([key, value]) => {
          if (value !== null) paths.add(`items.${i}.${key}`);
        }),
      );
      result.agenda.action_items.forEach((row, i) =>
        Object.entries(row).forEach(([key, value]) => {
          if (value !== null) paths.add(`action_items.${i}.${key}`);
        }),
      );
      setMarked(paths);
    } catch (error) {
      if (!active.signal.aborted)
        setError(error instanceof Error ? error.message : "Parsing failed.");
    } finally {
      if (controller.current === active) {
        setParsing(false);
        controller.current = null;
      }
    }
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSaved(false);
    if (
      agenda.starts_at &&
      (!Number.isFinite(Date.parse(agenda.starts_at)) ||
        !/(Z|[+-]\d{2}:\d{2})$/.test(agenda.starts_at))
    ) {
      setError(
        "Start must be an ISO date and time with an offset, e.g. 2026-10-19T10:00:00+03:00.",
      );
      setSaving(false);
      return;
    }
    try {
      const result = await agendaApi.save(id, agenda, original);
      queryClient.setQueryData(["agenda", id], result);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["meetings"] }),
        queryClient.invalidateQueries({ queryKey: ["meeting-stats"] }),
      ]);
      setSaved(true);
      setMarked(new Set());
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Could not save agenda.",
      );
    } finally {
      setSaving(false);
    }
  }
  if (!id)
    return (
      <div className="p-8">
        <Link href="/meetings">Choose a meeting first →</Link>
      </div>
    );
  return (
    <div className="mx-auto grid w-full max-w-4xl gap-6 px-6 py-10">
      <Link href="/meetings" className="text-sm underline">
        ← Meetings
      </Link>
      <header>
        <h1 className="text-3xl font-semibold">Meeting agenda</h1>
        <p className="mt-2 text-muted-foreground">
          {meeting.data?.meeting.title ?? "Loading meeting…"} · Paste notes or
          build your agenda by hand.
        </p>
      </header>
      {meeting.error && <p role="alert">{meeting.error.message}</p>}
      {!aiEnabled && (
        <p role="status" className="rounded-xl border bg-muted p-4 text-sm">
          AI parsing is switched off. You can add, edit and save your agenda
          below.
        </p>
      )}
      <section
        className="grid gap-4 rounded-xl border bg-card p-6 shadow-sm"
        aria-labelledby="paste-heading"
      >
        <h2 id="paste-heading" className="text-lg font-semibold">
          Paste an agenda
        </h2>
        <label htmlFor="pasted-text" className="text-sm">
          Email, chat message or meeting notes
        </label>
        <textarea
          id="pasted-text"
          rows={6}
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={parsing || saving}
          className="w-full rounded-lg border bg-background p-3"
          placeholder="Paste your agenda here…"
        />
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            onClick={() => void parse()}
            disabled={
              !aiEnabled ||
              !text.trim() ||
              text.length > 10000 ||
              parsing ||
              saving ||
              !meeting.data
            }
          >
            Parse
          </Button>
          {parsing && (
            <>
              <span role="status" className="text-sm">
                Reading your agenda… This can take a few seconds.
              </span>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  controller.current?.abort();
                  setParsing(false);
                }}
              >
                Cancel
              </Button>
            </>
          )}
          <span
            className={`text-xs ${text.length > 10000 ? "text-destructive" : "text-muted-foreground"}`}
          >
            {text.length.toLocaleString()} / 10,000 characters
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          Check every suggestion before saving. Cancelling stops waiting; a
          model call already started may still be billed.
        </p>
      </section>
      {error && (
        <p
          role="alert"
          className="rounded-lg border border-destructive p-4 text-sm text-destructive"
        >
          {error}
        </p>
      )}
      {saved && (
        <p role="status" className="rounded-lg border p-4 text-sm">
          Agenda saved.
        </p>
      )}
      <form
        onSubmit={save}
        className="grid gap-5 rounded-xl border bg-card p-6 shadow-sm"
      >
        <h2 className="text-lg font-semibold">Check and edit</h2>
        <p className="text-sm text-muted-foreground">
          Empty meeting fields keep the meeting’s current title, start and
          duration. You can always enter the agenda by hand.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="grid gap-2 text-sm">
            <span>Title{badge("title")}</span>
            <Input
              aria-label="Agenda title"
              value={agenda.title ?? ""}
              maxLength={200}
              disabled={parsing || saving}
              onChange={(e) =>
                update({ ...agenda, title: e.target.value || null }, "title")
              }
            />
          </label>
          <label className="grid gap-2 text-sm">
            <span>Start (ISO date, time and offset){badge("starts_at")}</span>
            <Input
              aria-label="Agenda start"
              placeholder="2026-10-19T10:00:00+03:00"
              value={agenda.starts_at ?? ""}
              disabled={parsing || saving}
              onChange={(e) =>
                update(
                  { ...agenda, starts_at: e.target.value || null },
                  "starts_at",
                )
              }
            />
          </label>
          <label className="grid gap-2 text-sm">
            <span>Duration (minutes){badge("duration_minutes")}</span>
            <Input
              type="number"
              min={1}
              max={600}
              value={agenda.duration_minutes ?? ""}
              disabled={parsing || saving}
              onChange={(e) =>
                update(
                  {
                    ...agenda,
                    duration_minutes: e.target.value
                      ? Number(e.target.value)
                      : null,
                  },
                  "duration_minutes",
                )
              }
            />
          </label>
          <label className="grid gap-2 text-sm">
            <span>Language{badge("language")}</span>
            <Input
              required
              pattern="[a-z]{2,3}(-[A-Za-z]{2,8})?"
              value={agenda.language}
              disabled={parsing || saving}
              onChange={(e) =>
                update({ ...agenda, language: e.target.value }, "language")
              }
            />
          </label>
        </div>
        <h3 className="font-medium">Agenda items</h3>
        {agenda.items.map((row, i) => (
          <fieldset
            key={i}
            disabled={parsing || saving}
            className="grid gap-3 rounded-lg border p-4 sm:grid-cols-3"
          >
            <legend className="text-sm">Item {i + 1}</legend>
            {(["topic", "owner", "minutes"] as const).map((key) => (
              <label key={key} className="grid gap-2 text-sm">
                <span>
                  {key}
                  {badge(`items.${i}.${key}`)}
                </span>
                <Input
                  aria-label={`Item ${i + 1} ${key}`}
                  required={key === "topic"}
                  type={key === "minutes" ? "number" : "text"}
                  min={1}
                  max={480}
                  maxLength={key === "owner" ? 200 : 2000}
                  value={row[key] ?? ""}
                  onChange={(e) =>
                    update(
                      {
                        ...agenda,
                        items: agenda.items.map((r, n) =>
                          n === i
                            ? {
                                ...r,
                                [key]:
                                  key === "minutes"
                                    ? e.target.value
                                      ? Number(e.target.value)
                                      : null
                                    : e.target.value || null,
                              }
                            : r,
                        ),
                      },
                      `items.${i}.${key}`,
                    )
                  }
                />
              </label>
            ))}
            <Button
              type="button"
              variant="outline"
              onClick={() => removeRow("items", i)}
            >
              Remove item {i + 1}
            </Button>
          </fieldset>
        ))}
        <Button
          type="button"
          variant="outline"
          disabled={parsing || saving || agenda.items.length >= 50}
          onClick={() =>
            update(
              {
                ...agenda,
                items: [
                  ...agenda.items,
                  { topic: "", owner: null, minutes: null },
                ],
              },
              "items",
            )
          }
        >
          Add agenda item
        </Button>
        <h3 className="font-medium">Action items</h3>
        {agenda.action_items.map((row, i) => (
          <fieldset
            key={i}
            disabled={parsing || saving}
            className="grid gap-3 rounded-lg border p-4 sm:grid-cols-3"
          >
            <legend className="text-sm">Action {i + 1}</legend>
            {(["task", "owner", "due"] as const).map((key) => (
              <label key={key} className="grid gap-2 text-sm">
                <span>
                  {key}
                  {badge(`action_items.${i}.${key}`)}
                </span>
                <Input
                  aria-label={`Action ${i + 1} ${key}`}
                  required={key === "task"}
                  type={key === "due" ? "date" : "text"}
                  maxLength={key === "owner" ? 200 : 2000}
                  value={row[key] ?? ""}
                  onChange={(e) =>
                    update(
                      {
                        ...agenda,
                        action_items: agenda.action_items.map((r, n) =>
                          n === i ? { ...r, [key]: e.target.value || null } : r,
                        ),
                      },
                      `action_items.${i}.${key}`,
                    )
                  }
                />
              </label>
            ))}
            <Button
              type="button"
              variant="outline"
              onClick={() => removeRow("action_items", i)}
            >
              Remove action {i + 1}
            </Button>
          </fieldset>
        ))}
        <Button
          type="button"
          variant="outline"
          disabled={parsing || saving || agenda.action_items.length >= 50}
          onClick={() =>
            update(
              {
                ...agenda,
                action_items: [
                  ...agenda.action_items,
                  { task: "", owner: null, due: null },
                ],
              },
              "action_items",
            )
          }
        >
          Add action item
        </Button>
        <Button type="submit" disabled={parsing || saving || !meeting.data}>
          {saving ? "Saving…" : "Save agenda"}
        </Button>
        {original && (
          <details className="text-xs text-muted-foreground">
            <summary>
              Original AI suggestion · {original.model} ·{" "}
              {original.prompt_version}
            </summary>
            <pre className="mt-3 overflow-auto whitespace-pre-wrap">
              {JSON.stringify(original, null, 2)}
            </pre>
          </details>
        )}
      </form>
    </div>
  );
}
