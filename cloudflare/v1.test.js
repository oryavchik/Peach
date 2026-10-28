import test from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import { routeV1, weekRange } from "./v1.js";
import { checkedAgenda } from "./worker.js";

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}
const helpers = {
  HttpError,
  checkedAgenda,
  body: (request) => request.json(),
  json: (value, status = 200) =>
    new Response(JSON.stringify(value), {
      status,
      headers: { "content-type": "application/json" },
    }),
};
function database() {
  const db = new DatabaseSync(":memory:");
  db.exec(
    readFileSync(
      new URL("./migrations/0001_initial.sql", import.meta.url),
      "utf8",
    ),
  );
  db.exec(
    readFileSync(
      new URL("./migrations/0002_original_app.sql", import.meta.url),
      "utf8",
    ),
  );
  return {
    db,
    env: {
      DB: {
        prepare(sql) {
          const statement = db.prepare(sql);
          let args = [];
          return {
            bind(...values) {
              args = values;
              return this;
            },
            async first() {
              return statement.get(...args) ?? null;
            },
            async all() {
              return { results: statement.all(...args) };
            },
            async run() {
              return statement.run(...args);
            },
          };
        },
      },
    },
  };
}
const request = (path, method = "GET", value) =>
  new Request("https://peach.test/api/v1" + path, {
    method,
    ...(value === undefined ? {} : { body: JSON.stringify(value) }),
  });
const meetingInput = (title) => ({
  title,
  starts_at: new Date().toISOString(),
  duration_minutes: 45,
  participant_count: 3,
});
test("original meeting/agenda contract persists corrections and scopes every access", async () => {
  const { db, env } = database();
  try {
    const create = await routeV1(
      request("/meetings", "POST", meetingInput("Original")),
      env,
      "owner",
      helpers,
    );
    assert.equal(create.status, 201);
    const row = await create.json();
    assert.equal(row.participant_count, 3);
    const suggested = {
      title: "Suggested",
      starts_at: null,
      duration_minutes: null,
      items: [{ topic: "Pricing", owner: "Olena", minutes: 15 }],
      action_items: [],
      language: "en",
    };
    const final = {
      ...suggested,
      title: "Corrected",
      items: [{ ...suggested.items[0], minutes: 20 }],
    };
    const original = {
      agenda: suggested,
      model: "test-model:free",
      prompt_version: "agenda-v2",
    };
    const saved = await routeV1(
      request(`/meetings/${row.id}/agenda`, "POST", {
        agenda: final,
        ai_suggestion: original,
      }),
      env,
      "owner",
      helpers,
    );
    assert.equal(saved.status, 200);
    const result = await (
      await routeV1(
        request(`/meetings/${row.id}/agenda`),
        env,
        "owner",
        helpers,
      )
    ).json();
    assert.equal(result.meeting.title, "Corrected");
    assert.equal(result.meeting.duration_minutes, 45);
    assert.equal(result.agenda.items[0].minutes, 20);
    assert.equal(result.ai_suggestion.agenda.items[0].minutes, 15);
    const foreign = await (
      await routeV1(request("/meetings"), env, "other", helpers)
    ).json();
    assert.equal(foreign.total, 0);
    await assert.rejects(
      () =>
        routeV1(request(`/meetings/${row.id}/agenda`), env, "other", helpers),
      (e) => e.status === 404,
    );
    assert.equal(
      (
        await routeV1(
          request(`/meetings/${row.id}`, "DELETE"),
          env,
          "owner",
          helpers,
        )
      ).status,
      204,
    );
  } finally {
    db.close();
  }
});
test("board CRUD supports status moves and protects another owner's items", async () => {
  const { db, env } = database();
  try {
    const row = await (
      await routeV1(
        request("/items", "POST", {
          name: "Write agenda",
          status: "todo",
          description: "Review",
        }),
        env,
        "owner",
        helpers,
      )
    ).json();
    const updated = await (
      await routeV1(
        request(`/items/${row.id}`, "PATCH", { status: "done" }),
        env,
        "owner",
        helpers,
      )
    ).json();
    assert.equal(updated.name, "Write agenda");
    assert.equal(updated.status, "done");
    await assert.rejects(
      () =>
        routeV1(request(`/items/${row.id}`, "DELETE"), env, "other", helpers),
      (e) => e.status === 404,
    );
    const list = await (
      await routeV1(request("/items?limit=100"), env, "owner", helpers)
    ).json();
    assert.equal(list.total, 1);
    assert.equal(
      (
        await routeV1(
          request(`/items/${row.id}`, "DELETE"),
          env,
          "owner",
          helpers,
        )
      ).status,
      204,
    );
  } finally {
    db.close();
  }
});
test("weekly totals and CSV include only the current owner's current week", async () => {
  const { db, env } = database();
  try {
    await routeV1(
      request("/meetings", "POST", meetingInput('Pricing, "Pro"')),
      env,
      "owner",
      helpers,
    );
    await routeV1(
      request("/meetings", "POST", meetingInput("Other owner")),
      env,
      "other",
      helpers,
    );
    const stats = await (
      await routeV1(request("/meetings/stats"), env, "owner", helpers)
    ).json();
    assert.equal(stats.meeting_count, 1);
    assert.equal(stats.total_hours, 0.75);
    const csv = await (
      await routeV1(request("/meetings/report.csv"), env, "owner", helpers)
    ).text();
    assert.ok(csv.includes('"Pricing, ""Pro"""'));
    assert.ok(!csv.includes("Other owner"));
    const dates = weekRange(new Date("2026-10-28T10:00:00Z"));
    assert.equal(dates.start, "2026-10-26T00:00:00.000Z");
  } finally {
    db.close();
  }
});
test("invalid creation never persists a partial meeting", async () => {
  const { db, env } = database();
  try {
    await assert.rejects(
      () =>
        routeV1(
          request("/meetings", "POST", {
            ...meetingInput("Bad"),
            duration_minutes: 0,
          }),
          env,
          "owner",
          helpers,
        ),
      (e) => e.status === 422,
    );
    assert.equal(db.prepare("SELECT COUNT(*) AS n FROM meetings").get().n, 0);
  } finally {
    db.close();
  }
});
