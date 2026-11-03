import test from "node:test";
import assert from "node:assert/strict";
import {escapeHtml, bytes, filteredJobs, active, attention, displayValue, dateLabel} from "../src/knoa_parse/apps/console/static/model.mjs";

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
