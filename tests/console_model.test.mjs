import test from "node:test";
import assert from "node:assert/strict";
import {escapeHtml, bytes, filteredJobs, active, attention, displayValue, dateLabel, clipId, diagnosticMessage, addDiagnostic, eventTimeLabel} from "../src/knoa_parse/apps/console/static/model.mjs";

test("untrusted evidence and filenames stay text", () => {
  assert.equal(escapeHtml('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
  assert.equal(escapeHtml("'&"), "&#39;&amp;");
});
test("partial is an attention state, not completed or active", () => {
  assert.equal(attention("partial"), true);
  assert.equal(active("partial"), false);
  assert.equal(attention("succeeded"), false);
  assert.equal(active("queued"), true);
});
test("search filters only the supplied recent window and matches names and IDs", () => {
  const jobs = [{id:"abc",state:"queued",source:{filename:"中文预算.xlsx"}}, {id:"def",state:"partial",source:{filename:"report.pdf"}}];
  assert.deepEqual(filteredJobs(jobs,"all","预算").map(job=>job.id), ["abc"]);
  assert.deepEqual(filteredJobs(jobs,"attention","").map(job=>job.id), ["def"]);
  assert.equal(filteredJobs(jobs,"active","def").length,0);
  assert.deepEqual(filteredJobs(jobs,"all","DEF").map(job=>job.id), ["def"]);
});
test("display keeps false, zero, missing size and missing time distinct", () => {
  assert.equal(displayValue(false), "false");
  assert.equal(displayValue(0), "0");
  assert.equal(displayValue(null), "null");
  assert.equal(bytes(0), "0 B");
  assert.equal(bytes(undefined), "大小未知");
  assert.equal(dateLabel(undefined), "时间未知");
});
test("diagnostic values stay bounded and redact credentials", () => {
  assert.equal(clipId("abcdefghijklm", 9), "abcd…jklm");
  assert.equal(diagnosticMessage("Bearer super-secret api_key=abc123"), "Bearer [已隐藏] api_key=[已隐藏]");
  let events = [];
  for (let index = 0; index < 105; index += 1) events = addDiagnostic(events, {kind:"sync", message:`event-${index}`}, 100);
  assert.equal(events.length, 100);
  assert.equal(events[0].message, "event-5");
  assert.match(eventTimeLabel(events.at(-1).at), /^\d{2}:\d{2}:\d{2}$/);
});
test("diagnostics redact quoted, whitespace, header and URL credentials", () => {
  const inputs = [
    '{"api_key":"synthetic secret with spaces", "message":"failure"}',
    "{'client_secret': 'synthetic secret with spaces'}",
    '"Authorization": "Bearer synthetic-key with-spaces"',
    "Authorization: Basic c3ludGhldGljLWtleQ==",
    "x-api-key='synthetic secret with spaces'",
    "password=synthetic secret with spaces; operation failed",
    "secret synthetic secret with spaces",
    "https://synthetic-user:synthetic-password@example.test/v1?api_key=synthetic-key&task=one",
    "https://example.test/v1?access_token=synthetic-key&task=one",
    'Bearer "synthetic secret with spaces"',
  ];
  for (const value of inputs) {
    const redacted = diagnosticMessage(value);
    assert.ok(!/synthetic|c3ludGhldGlj/i.test(redacted), `${value} -> ${redacted}`);
    assert.match(redacted, /已隐藏/);
  }
  assert.equal(diagnosticMessage({api_key:"synthetic-key"}), "");
  assert.equal(diagnosticMessage("安全摘要"), "安全摘要");
  assert.equal(diagnosticMessage("x".repeat(10000)).length, 256);
});
test("diagnostic buffers enforce count, field and metadata boundaries", () => {
  const malicious = {id:'<img onerror="alert(1)">', at:-1, kind:"untrusted-kind", message:"m".repeat(1000), detail:"d".repeat(1000), api_key:"synthetic-key"};
  const entry = addDiagnostic([], malicious)[0];
  assert.match(entry.id, /^\d{13}-\d+$/);
  assert.ok(entry.at > 0);
  assert.equal(entry.kind, "info");
  assert.equal(entry.message.length, 160);
  assert.equal(entry.detail.length, 256);
  assert.ok(!Object.hasOwn(entry, "api_key"));
  for (const limit of [undefined, 0, -10, NaN, Infinity, 10000, .5]) {
    let events = [];
    for (let index = 0; index < 110; index += 1) events = addDiagnostic(events, {kind:"同步", message:`event-${index}`}, limit);
    assert.ok(events.length >= 1 && events.length <= 100, `invalid buffer size for ${limit}`);
    assert.equal(events.at(-1).message, "event-109");
  }
  assert.equal(addDiagnostic(null, {kind:"错误", message:"安全摘要"}).length, 1);
  const [retained] = addDiagnostic([{...malicious, kind:"错误"}], {kind:"同步", message:"new"});
  assert.equal(retained.message.length, 160);
  assert.equal(retained.detail.length, 256);
});
