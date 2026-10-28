import Ajv from "ajv";
import addFormats from "ajv-formats";
import schema from "./agenda.schema.json" with { type: "json" };
import prompt from "./prompt.json" with { type: "json" };

const ajv = new Ajv({ strict: false });
addFormats(ajv);
const validate = ajv.compile(schema);
const encoder = new TextEncoder();
const MODEL = "cohere/north-mini-code:free";
const COOKIE = "__Host-peach-session";

class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
const json = (body, status = 200, headers = {}) => new Response(JSON.stringify(body), {
  status, headers: { "content-type": "application/json", "cache-control": "no-store", ...headers },
});
const b64 = bytes => btoa(String.fromCharCode(...new Uint8Array(bytes)))
  .replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
const un64 = text => Uint8Array.from(atob(text.replaceAll("-", "+").replaceAll("_", "/")), c => c.charCodeAt(0));
async function key(secret) {
  return crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}
async function session(env) {
  const payload = b64(encoder.encode(JSON.stringify({ sub: "owner", exp: Math.floor(Date.now() / 1000) + 43200 })));
  const signature = await crypto.subtle.sign("HMAC", await key(env.SESSION_SECRET), encoder.encode(payload));
  return `${payload}.${b64(signature)}`;
}
async function authenticate(request, env) {
  const token = request.headers.get("cookie")?.split(";").map(s => s.trim())
    .find(s => s.startsWith(`${COOKIE}=`))?.slice(COOKIE.length + 1);
  try {
    const [payload, signature, extra] = token.split(".");
    if (extra || !await crypto.subtle.verify("HMAC", await key(env.SESSION_SECRET), un64(signature), encoder.encode(payload))) throw 0;
    const claims = JSON.parse(new TextDecoder().decode(un64(payload)));
    if (claims.sub !== "owner" || claims.exp <= Date.now() / 1000) throw 0;
    return claims.sub;
  } catch { throw new HttpError(401, "Увійди за паролем демонстрації."); }
}
async function body(request) {
  let size = 0;
  const chunks = [];
  const reader = request.body?.getReader();
  if (!reader) throw new HttpError(422, "Потрібен JSON.");
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > 100000) { await reader.cancel(); throw new HttpError(413, "Запит надто довгий."); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  try { return JSON.parse(new TextDecoder().decode(bytes)); }
  catch { throw new HttpError(422, "Невалідний JSON."); }
}
async function quota(env, bucket, limit) {
  const row = await env.DB.prepare(`INSERT INTO quotas(bucket,count) VALUES (?1,1)
    ON CONFLICT(bucket) DO UPDATE SET count=count+1 WHERE count < ?2 RETURNING count`)
    .bind(bucket, limit).first();
  if (!row) throw new HttpError(429, "Ліміт безкоштовної демонстрації вичерпано. Спробуй пізніше або введи agenda вручну.");
}
export function dateContext(today) {
  const date = new Date(`${today}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(today) || !Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== today)
    throw new HttpError(422, "Невалідна дата today.");
  const index = (date.getUTCDay() + 6) % 7;
  const names = ["Monday / понеділок / Пн", "Tuesday / вівторок / Вт", "Wednesday / середа / Ср", "Thursday / четвер / Чт", "Friday / п'ятниця / Пт", "Saturday / субота / Сб", "Sunday / неділя / Нд"];
  const shifted = days => new Date(date.getTime() + days * 86400000).toISOString().slice(0, 10);
  return { today_weekday: names[index], reference_dates: {
    ...Object.fromEntries(names.map((name, i) => [name, shifted((i - index + 7) % 7 || 7)])),
    end_of_week: shifted(6 - index),
  } };
}
export function checkedAgenda(value, source) {
  if (!validate(value)) throw new Error("Поля не відповідають схемі: " + ajv.errorsText(validate.errors));
  if (source && [...value.items, ...(value.action_items || [])].some(row => row.owner && !source.includes(row.owner)))
    throw new Error("Owner має дослівно бути в тексті.");
  return { title: null, starts_at: null, duration_minutes: null, action_items: [], ...value };
}
async function parse(input, env, user) {
  if (typeof input.text !== "string" || !input.text.trim()) throw new HttpError(422, "Встав текст agenda.");
  if ([...input.text].length > 10000) throw new HttpError(413, "Максимум 10 000 символів.");
  try { new Intl.DateTimeFormat("en", { timeZone: input.tz }).format(); }
  catch { throw new HttpError(422, "Невалідна часова зона."); }
  if (typeof input.tz !== "string" || typeof input.today !== "string") throw new HttpError(422, "Потрібні today і tz.");
  const context = dateContext(input.today);
  const messages = [{ role: "system", content: prompt.system }, { role: "user", content: JSON.stringify({
    today: input.today, timezone: input.tz, ...context, pasted_text: input.text,
  }) }];
  const usage = { input_tokens: 0, output_tokens: 0 };
  let model = MODEL, status = 200;
  const started = Date.now();
  try {
    if (!env.OPENROUTER_API_KEY) throw new HttpError(503, "Безкоштовну модель ще не налаштовано.");
    for (let attempt = 0; attempt < 2; attempt++) {
      await quota(env, `parse:${new Date().toISOString().slice(0, 10)}`, 40);
      let response;
      try {
        response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
          method: "POST", signal: AbortSignal.timeout(25000),
          headers: { Authorization: `Bearer ${env.OPENROUTER_API_KEY}`, "Content-Type": "application/json" },
          body: JSON.stringify({ model: MODEL, messages, max_tokens: 4096, temperature: 0,
            reasoning: { enabled: false }, parallel_tool_calls: false, tool_choice: "required",
            tools: [{ type: "function", function: { name: "record_agenda", description: "Extract an agenda without saving it.", parameters: schema } }],
          }),
        });
      } catch { throw new HttpError(503, "Безкоштовна модель не відповідає. Спробуй ще або введи agenda вручну."); }
      if (!response.ok) throw new HttpError(response.status === 429 ? 429 : 503, response.status === 429
        ? "Безкоштовна квота зайнята. Спробуй пізніше." : "Безкоштовна модель тимчасово недоступна.");
      const result = await response.json();
      usage.input_tokens += result.usage?.prompt_tokens || 0;
      usage.output_tokens += result.usage?.completion_tokens || 0;
      model = result.model || MODEL;
      const choice = result.choices?.[0], calls = choice?.message?.tool_calls;
      if (choice?.finish_reason === "length" || calls?.length !== 1 || calls[0].function?.name !== "record_agenda")
        throw new HttpError(422, "Модель не повернула одну agenda. Введи її вручну або спробуй ще.");
      let agenda;
      try { agenda = checkedAgenda(JSON.parse(calls[0].function.arguments), input.text); }
      catch (error) {
        if (attempt) throw new HttpError(422, "Модель двічі повернула невалідні поля. Введи agenda вручну.");
        messages.push(choice.message, { role: "tool", tool_call_id: calls[0].id,
          content: "Validation failed. Match the schema, copy owners literally and leave missing values null." });
        continue;
      }
      if (!agenda.items.length && !agenda.action_items.length) throw new HttpError(422, "У цьому тексті не знайдено agenda зустрічі.");
      return { agenda, model, prompt_version: prompt.version, ...usage, latency_ms: Date.now() - started, cost_usd: 0 };
    }
  } catch (error) { status = error.status || 503; throw error; }
  finally {
    console.log(JSON.stringify({ event: "agenda_parsed", user, model, prompt_version: prompt.version,
      ...usage, latency_ms: Date.now() - started, cost_usd: 0, status }));
  }
}
async function route(request, env) {
  const url = new URL(request.url);
  if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
  if (request.method !== "GET" && request.headers.get("origin") !== url.origin)
    throw new HttpError(403, "Запит має надходити з цього сайту.");
  if (url.pathname === "/api/login" && request.method === "POST") {
    if (!env.DEMO_PASSWORD || !env.SESSION_SECRET) throw new HttpError(503, "Вхід ще не налаштовано.");
    const hash = b64(await crypto.subtle.digest("SHA-256", encoder.encode(request.headers.get("CF-Connecting-IP") || "local")));
    await quota(env, `login:${Math.floor(Date.now() / 600000)}:${hash}`, 10);
    const input = await body(request);
    const actual = await crypto.subtle.sign("HMAC", await key(env.SESSION_SECRET), encoder.encode(String(input.password || "")));
    const valid = await crypto.subtle.verify("HMAC", await key(env.SESSION_SECRET), actual, encoder.encode(env.DEMO_PASSWORD));
    if (!valid) throw new HttpError(401, "Неправильний пароль демонстрації.");
    return json({ ok: true }, 200, { "set-cookie": `${COOKIE}=${await session(env)}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=43200` });
  }
  if (url.pathname === "/api/logout" && request.method === "POST")
    return json({ ok: true }, 200, { "set-cookie": `${COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0` });
  const owner = await authenticate(request, env);
  if (url.pathname === "/api/me" && request.method === "GET") return json({ owner });
  if (url.pathname === "/api/parse" && request.method === "POST") return json(await parse(await body(request), env, owner));
  if (url.pathname === "/api/meetings" && request.method === "GET") {
    const rows = await env.DB.prepare("SELECT id,title,updated_at FROM meetings WHERE owner=?1 ORDER BY updated_at DESC LIMIT 100").bind(owner).all();
    return json({ items: rows.results });
  }
  if (url.pathname === "/api/meetings" && request.method === "POST") {
    const input = await body(request), title = String(input.title || "").trim();
    if (!title || title.length > 200) throw new HttpError(422, "Назва: від 1 до 200 символів.");
    const id = crypto.randomUUID();
    await env.DB.prepare("INSERT INTO meetings(id,owner,title,updated_at) VALUES(?1,?2,?3,?4)").bind(id,owner,title,new Date().toISOString()).run();
    return json({ id, title }, 201);
  }
  const match = url.pathname.match(/^\/api\/meetings\/([a-z0-9-]+)\/agenda$/);
  if (match) {
    const meeting = await env.DB.prepare("SELECT * FROM meetings WHERE id=?1 AND owner=?2").bind(match[1],owner).first();
    if (!meeting) throw new HttpError(404, "Зустріч не знайдено.");
    if (request.method === "GET") return json({ id: meeting.id, title: meeting.title,
      agenda: meeting.agenda ? JSON.parse(meeting.agenda) : null,
      ai_suggestion: meeting.ai_suggestion ? JSON.parse(meeting.ai_suggestion) : null });
    if (request.method === "POST") {
      const input = await body(request);
      try {
        checkedAgenda(input.agenda);
        if (input.ai_suggestion) {
          checkedAgenda(input.ai_suggestion.agenda);
          if (typeof input.ai_suggestion.model !== "string" || typeof input.ai_suggestion.prompt_version !== "string") throw new Error();
        }
      } catch { throw new HttpError(422, "Перевір поля agenda перед збереженням."); }
      await env.DB.prepare("UPDATE meetings SET title=?1,agenda=?2,ai_suggestion=?3,updated_at=?4 WHERE id=?5 AND owner=?6")
        .bind(input.agenda.title || meeting.title,JSON.stringify(input.agenda),input.ai_suggestion ? JSON.stringify(input.ai_suggestion) : null,new Date().toISOString(),match[1],owner).run();
      return json({ ok: true });
    }
  }
  throw new HttpError(404, "Endpoint не знайдено.");
}
export default {
  async fetch(request, env) {
    try {
      if (new URL(request.url).protocol !== "https:") {
        const secure = new URL(request.url); secure.protocol = "https:";
        return Response.redirect(secure.toString(), 308);
      }
      const result = await route(request, env);
      const response = new Response(result.body, result);
      response.headers.set("X-Content-Type-Options", "nosniff");
      response.headers.set("Referrer-Policy", "same-origin");
      response.headers.set("Strict-Transport-Security", "max-age=31536000");
      response.headers.set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
      return response;
    }
    catch (error) {
      if (!error.status) console.error("request_failed", error.name || "Error");
      return json({ error: error.status ? error.message : "Сервіс тимчасово недоступний. Спробуй пізніше." }, error.status || 503);
    }
  },
};
