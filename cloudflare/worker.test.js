import test from "node:test";
import assert from "node:assert/strict";
import worker, { checkedAgenda, dateContext } from "./worker.js";

test("relative weekday context has concrete future dates and Sunday week end", () => {
  const context = dateContext("2026-10-15");
  assert.equal(context.reference_dates["Monday / понеділок / Пн"], "2026-10-19");
  assert.equal(context.reference_dates.end_of_week, "2026-10-18");
  assert.throws(() => dateContext("2026-02-30"));
});
test("invalid model data and invented owners cannot escape validation", () => {
  const value = {items:[{topic:"Pricing",owner:"Olena",minutes:15}],language:"en"};
  assert.equal(checkedAgenda(value,"Pricing Olena").action_items.length,0);
  assert.throws(() => checkedAgenda(value,"Pricing Taras"));
  assert.throws(() => checkedAgenda({...value,duration_minutes:999}));
  assert.throws(() => checkedAgenda({...value,starts_at:"2026-10-19T10:00:00"}));
});
test("unsigned parse never reaches model or database", async () => {
  const result = await worker.fetch(new Request("https://peach.example/api/parse",{
    method:"POST",headers:{origin:"https://peach.example"},body:"{}",
  }),{SESSION_SECRET:"test-only-secret"});
  assert.equal(result.status,401);
});
test("foreign origin cannot mutate data even with a session",async () => {
  const result = await worker.fetch(new Request("https://peach.example/api/meetings",{
    method:"POST",headers:{origin:"https://other.example"},body:"{}",
  }),{});
  assert.equal(result.status,403);
});
