const meeting = (row) => ({
  id: row.id,
  title: row.title,
  starts_at: row.starts_at,
  duration_minutes: row.duration_minutes,
  participant_count: row.participant_count,
  created_at: row.created_at,
});
const item = (row) => ({
  id: row.id,
  name: row.name,
  description: row.description,
  status: row.status,
  created_at: row.created_at,
  updated_at: row.updated_at,
});
const statuses = new Set(["todo", "in_progress", "done"]);
function integer(value, min, max, fail) {
  if (!Number.isInteger(value) || value < min || value > max)
    fail("Invalid integer field.");
  return value;
}
function text(value, min, max, fail) {
  if (
    typeof value !== "string" ||
    value.trim().length < min ||
    value.length > max
  )
    fail("Invalid text field.");
  return value.trim();
}
export function weekRange(now = new Date()) {
  const start = new Date(now);
  start.setUTCHours(0, 0, 0, 0);
  start.setUTCDate(start.getUTCDate() - ((start.getUTCDay() + 6) % 7));
  const end = new Date(start.getTime() + 7 * 86400000),
    previous = new Date(start.getTime() - 7 * 86400000);
  return {
    start: start.toISOString(),
    end: end.toISOString(),
    previous: previous.toISOString(),
  };
}
export async function routeV1(request, env, owner, helpers) {
  const { json, body, checkedAgenda, HttpError } = helpers,
    url = new URL(request.url),
    method = request.method,
    path = url.pathname;
  const fail = (message) => {
    throw new HttpError(422, message);
  };
  const page = () => ({
    limit: integer(Number(url.searchParams.get("limit") || 20), 1, 100, fail),
    offset: integer(
      Number(url.searchParams.get("offset") || 0),
      0,
      2147483647,
      fail,
    ),
  });
  const findMeeting = async (id) => {
    const row = await env.DB.prepare(
      "SELECT * FROM meetings WHERE id=?1 AND owner=?2",
    )
      .bind(id, owner)
      .first();
    if (!row) throw new HttpError(404, "Meeting not found");
    return row;
  };
  if (path === "/api/v1/health/ready" && method === "GET") {
    await env.DB.prepare("SELECT 1 AS ready").first();
    return json({ status: "ok", database: "ok" });
  }
  if (path === "/api/v1/meetings/stats" && method === "GET") {
    const { start, end, previous } = weekRange();
    const total = async (lower, upper) =>
      env.DB.prepare(
        "SELECT COUNT(*) AS count,COALESCE(SUM(duration_minutes),0)/60.0 AS hours FROM meetings WHERE owner=?1 AND julianday(starts_at)>=julianday(?2) AND julianday(starts_at)<julianday(?3)",
      )
        .bind(owner, lower, upper)
        .first();
    const [current, last] = await Promise.all([
      total(start, end),
      total(previous, start),
    ]);
    return json({
      week_start: start,
      week_end: end,
      meeting_count: current.count,
      total_hours: current.hours,
      previous_meeting_count: last.count,
      previous_total_hours: last.hours,
    });
  }
  if (path === "/api/v1/meetings/report.csv" && method === "GET") {
    const { start, end } = weekRange();
    const rows = await env.DB.prepare(
      "SELECT title,starts_at,duration_minutes,participant_count FROM meetings WHERE owner=?1 AND julianday(starts_at)>=julianday(?2) AND julianday(starts_at)<julianday(?3) ORDER BY starts_at,id",
    )
      .bind(owner, start, end)
      .all();
    const cell = (value) =>
      '"' +
      String(/^[=+@-]/.test(String(value)) ? "'" + value : value).replaceAll(
        '"',
        '""',
      ) +
      '"';
    const csv = [
      "title,starts_at,duration_minutes,participant_count",
      ...rows.results.map((r) =>
        [r.title, r.starts_at, r.duration_minutes, r.participant_count]
          .map(cell)
          .join(","),
      ),
    ].join("\r\n");
    return new Response("\ufeff" + csv, {
      headers: {
        "content-type": "text/csv; charset=utf-8",
        "content-disposition": `attachment; filename="peach-week-${start.slice(0, 10)}.csv"`,
        "cache-control": "no-store",
      },
    });
  }
  if (path === "/api/v1/meetings") {
    if (method === "GET") {
      const { limit, offset } = page();
      const [rows, total] = await Promise.all([
        env.DB.prepare(
          "SELECT * FROM meetings WHERE owner=?1 ORDER BY starts_at DESC,id LIMIT ?2 OFFSET ?3",
        )
          .bind(owner, limit, offset)
          .all(),
        env.DB.prepare("SELECT COUNT(*) AS total FROM meetings WHERE owner=?1")
          .bind(owner)
          .first(),
      ]);
      return json({ items: rows.results.map(meeting), total: total.total });
    }
    if (method === "POST") {
      const input = await body(request),
        title = text(input.title, 1, 200, fail);
      const start = new Date(input.starts_at);
      if (
        typeof input.starts_at !== "string" ||
        !/(Z|[+-]\d\d:\d\d)$/i.test(input.starts_at) ||
        !Number.isFinite(start.getTime())
      )
        fail("Provide an ISO start time with a timezone offset.");
      const minutes = integer(input.duration_minutes, 1, 1440, fail),
        participants = integer(input.participant_count, 1, 2147483647, fail);
      const id = crypto.randomUUID(),
        now = new Date().toISOString();
      await env.DB.prepare(
        "INSERT INTO meetings(id,owner,title,starts_at,duration_minutes,participant_count,created_at,updated_at) VALUES(?1,?2,?3,?4,?5,?6,?7,?7)",
      )
        .bind(id, owner, title, start.toISOString(), minutes, participants, now)
        .run();
      return json(meeting(await findMeeting(id)), 201);
    }
  }
  const agendaMatch = path.match(/^\/api\/v1\/meetings\/([a-z0-9-]+)\/agenda$/);
  if (agendaMatch) {
    let row = await findMeeting(agendaMatch[1]);
    const result = () => {
      const suggestion = row.ai_suggestion
        ? JSON.parse(row.ai_suggestion)
        : null;
      return {
        meeting: meeting(row),
        agenda: row.agenda ? checkedAgenda(JSON.parse(row.agenda)) : null,
        ai_suggestion: suggestion
          ? { ...suggestion, agenda: checkedAgenda(suggestion.agenda) }
          : null,
      };
    };
    if (method === "GET") return json(result());
    if (method === "POST") {
      const input = await body(request);
      let agenda;
      try {
        agenda = checkedAgenda(input.agenda);
        if (input.ai_suggestion) {
          checkedAgenda(input.ai_suggestion.agenda);
          if (
            typeof input.ai_suggestion.model !== "string" ||
            typeof input.ai_suggestion.prompt_version !== "string"
          )
            throw new Error();
        }
      } catch {
        fail("Check agenda fields before saving.");
      }
      await env.DB.prepare(
        "UPDATE meetings SET title=?1,starts_at=?2,duration_minutes=?3,agenda=?4,ai_suggestion=?5,updated_at=?6 WHERE id=?7 AND owner=?8",
      )
        .bind(
          agenda.title || row.title,
          agenda.starts_at || row.starts_at,
          agenda.duration_minutes || row.duration_minutes,
          JSON.stringify(agenda),
          input.ai_suggestion ? JSON.stringify(input.ai_suggestion) : null,
          new Date().toISOString(),
          row.id,
          owner,
        )
        .run();
      row = await findMeeting(row.id);
      return json(result());
    }
  }
  const meetingMatch = path.match(/^\/api\/v1\/meetings\/([a-z0-9-]+)$/);
  if (meetingMatch && method === "DELETE") {
    await findMeeting(meetingMatch[1]);
    await env.DB.prepare("DELETE FROM meetings WHERE id=?1 AND owner=?2")
      .bind(meetingMatch[1], owner)
      .run();
    return new Response(null, { status: 204 });
  }
  if (path === "/api/v1/items") {
    if (method === "GET") {
      const { limit, offset } = page();
      const [rows, total] = await Promise.all([
        env.DB.prepare(
          "SELECT * FROM items WHERE owner=?1 ORDER BY created_at DESC,id LIMIT ?2 OFFSET ?3",
        )
          .bind(owner, limit, offset)
          .all(),
        env.DB.prepare("SELECT COUNT(*) AS total FROM items WHERE owner=?1")
          .bind(owner)
          .first(),
      ]);
      return json({ items: rows.results.map(item), total: total.total });
    }
    if (method === "POST") {
      const input = await body(request),
        name = text(input.name, 1, 120, fail);
      if (input.description != null) text(input.description, 0, 2000, fail);
      if (!statuses.has(input.status)) fail("Invalid item status.");
      const id = crypto.randomUUID(),
        now = new Date().toISOString();
      await env.DB.prepare(
        "INSERT INTO items(id,owner,name,description,status,created_at,updated_at) VALUES(?1,?2,?3,?4,?5,?6,?6)",
      )
        .bind(id, owner, name, input.description ?? null, input.status, now)
        .run();
      return json(
        item(
          await env.DB.prepare("SELECT * FROM items WHERE id=?1 AND owner=?2")
            .bind(id, owner)
            .first(),
        ),
        201,
      );
    }
  }
  const itemMatch = path.match(/^\/api\/v1\/items\/([a-z0-9-]+)$/);
  if (itemMatch) {
    const row = await env.DB.prepare(
      "SELECT * FROM items WHERE id=?1 AND owner=?2",
    )
      .bind(itemMatch[1], owner)
      .first();
    if (!row) throw new HttpError(404, "Item not found");
    if (method === "DELETE") {
      await env.DB.prepare("DELETE FROM items WHERE id=?1 AND owner=?2")
        .bind(row.id, owner)
        .run();
      return new Response(null, { status: 204 });
    }
    if (method === "PATCH") {
      const input = await body(request);
      const name =
        input.name === undefined ? row.name : text(input.name, 1, 120, fail);
      const description =
        input.description === undefined ? row.description : input.description;
      if (description != null) text(description, 0, 2000, fail);
      const status = input.status === undefined ? row.status : input.status;
      if (!statuses.has(status)) fail("Invalid item status.");
      await env.DB.prepare(
        "UPDATE items SET name=?1,description=?2,status=?3,updated_at=?4 WHERE id=?5 AND owner=?6",
      )
        .bind(
          name,
          description,
          status,
          new Date().toISOString(),
          row.id,
          owner,
        )
        .run();
      return json(
        item(
          await env.DB.prepare("SELECT * FROM items WHERE id=?1 AND owner=?2")
            .bind(row.id, owner)
            .first(),
        ),
      );
    }
  }
  throw new HttpError(404, "Endpoint not found");
}
