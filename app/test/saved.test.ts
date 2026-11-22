// Run: npm test. Open in Calendar opens only the .ics the save dialog returned this session (D-98).
import assert from "node:assert/strict";
import { test } from "node:test";
import { savedCalendar } from "../electron/saved.ts";

const make = () => {
  const opened: string[] = [];
  return { opened, cal: savedCalendar(async (f) => (opened.push(f), "")) };
};
test("nothing is opened before a save", async () => {
  const { opened, cal } = make();
  assert.equal(await cal.openLast(), false);
  assert.deepEqual(opened, []);
});
test("opens exactly the path the save returned", async () => {
  const { opened, cal } = make();
  cal.remember("/x/a_deadlines.ics", "ics");
  assert.equal(await cal.openLast(), true);
  assert.deepEqual(opened, ["/x/a_deadlines.ics"]);
});
test("a CSV save, or a path that is not .ics, is never opened", async () => {
  const { opened, cal } = make();
  cal.remember("/x/a_fields.csv", "csv");
  cal.remember("/x/evil.app", "ics");
  assert.equal(await cal.openLast(), false);
  assert.deepEqual(opened, []);
});
test("a failed open reports false", async () => {
  const cal = savedCalendar(async () => "no app");
  cal.remember("/x/a.ics", "ics");
  assert.equal(await cal.openLast(), false);
});
