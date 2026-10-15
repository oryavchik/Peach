import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgendaEditor } from "@/components/agenda-editor";
import { agendaApi } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("meeting=meeting-1"),
}));
vi.mock("@/lib/api", () => ({
  agendaApi: { get: vi.fn(), parse: vi.fn(), save: vi.fn() },
}));
const agenda = {
  title: "Pricing",
  starts_at: null,
  duration_minutes: 45,
  items: [{ topic: "Plans", owner: "Olena", minutes: 15 }],
  action_items: [],
  language: "en",
};
const suggestion = {
  agenda,
  model: "test-model",
  prompt_version: "agenda-v1",
  input_tokens: 100,
  output_tokens: 50,
  cost_usd: 0.00154,
  latency_ms: 900,
};
const initial = {
  meeting: { title: "Weekly sync" },
  agenda: null,
  ai_suggestion: null,
};
function mount() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <AgendaEditor />
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.resetAllMocks();
  vi.stubEnv("NEXT_PUBLIC_AGENDA_PARSER_ENABLED", "true");
  vi.mocked(agendaApi.get).mockResolvedValue(initial as never);
  vi.mocked(agendaApi.parse).mockResolvedValue(structuredClone(suggestion));
  vi.mocked(agendaApi.save).mockResolvedValue({
    ...initial,
    agenda,
    ai_suggestion: suggestion,
  } as never);
});

describe("agenda review", () => {
  it("disables paid parsing while preserving the manual form", async () => {
    vi.stubEnv("NEXT_PUBLIC_AGENDA_PARSER_ENABLED", "false");
    mount();
    await screen.findByText(/Weekly sync/);
    expect(screen.getByRole("button", { name: "Parse" })).toBeDisabled();
    expect(screen.getByText(/AI parsing is switched off/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Add agenda item" }),
    ).toBeEnabled();
    expect(agendaApi.parse).not.toHaveBeenCalled();
  });

  it("keeps the original suggestion while saving a corrected title", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByText(/Weekly sync/);
    await user.type(
      screen.getByLabelText("Email, chat message or meeting notes"),
      "Pricing sync Olena",
    );
    await user.click(screen.getByRole("button", { name: "Parse" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Agenda title")).toHaveValue("Pricing"),
    );
    expect(screen.getAllByText("suggested")).toHaveLength(6);
    await user.clear(screen.getByLabelText("Agenda title"));
    await user.type(screen.getByLabelText("Agenda title"), "Corrected pricing");
    expect(screen.getAllByText("suggested")).toHaveLength(5);
    await user.click(screen.getByRole("button", { name: "Save agenda" }));
    await screen.findByText("Agenda saved.");
    expect(agendaApi.save).toHaveBeenCalledWith(
      "meeting-1",
      { ...agenda, title: "Corrected pricing" },
      suggestion,
    );
  });
  it("supports manual saving when the model fails", async () => {
    vi.mocked(agendaApi.parse).mockRejectedValue(
      new Error("The model is unavailable."),
    );
    const user = userEvent.setup();
    mount();
    await screen.findByText(/Weekly sync/);
    await user.type(
      screen.getByLabelText("Email, chat message or meeting notes"),
      "sync",
    );
    await user.click(screen.getByRole("button", { name: "Parse" }));
    await screen.findByRole("alert");
    await user.click(screen.getByRole("button", { name: "Add agenda item" }));
    await user.type(screen.getByLabelText("Item 1 topic"), "Manual topic");
    await user.click(screen.getByRole("button", { name: "Save agenda" }));
    await screen.findByText("Agenda saved.");
    expect(agendaApi.save).toHaveBeenCalledWith(
      "meeting-1",
      expect.objectContaining({
        items: [{ topic: "Manual topic", owner: null, minutes: null }],
      }),
      null,
    );
  });
  it("aborts a pending parse and leaves manual editing available", async () => {
    vi.mocked(agendaApi.parse).mockImplementation(() => new Promise(() => {}));
    const user = userEvent.setup();
    mount();
    await screen.findByText(/Weekly sync/);
    await user.type(
      screen.getByLabelText("Email, chat message or meeting notes"),
      "sync",
    );
    await user.click(screen.getByRole("button", { name: "Parse" }));
    const signal = vi.mocked(agendaApi.parse).mock.calls[0][1];
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(signal.aborted).toBe(true);
    expect(screen.getByLabelText("Agenda title")).toBeEnabled();
  });
});
