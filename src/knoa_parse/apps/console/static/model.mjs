export const states = {
  queued: {label: "等待执行", tone: "queued"}, running: {label: "解析中", tone: "running"},
  succeeded: {label: "已完成", tone: "succeeded"}, partial: {label: "部分完成", tone: "partial"},
  failed: {label: "解析失败", tone: "failed"}, cancelled: {label: "已取消", tone: "cancelled"},
};
export const active = state => state === "queued" || state === "running";
export const attention = state => state === "partial" || state === "failed";
export const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
export const extension = name => (String(name || "").split(".").pop() || "FILE").toLowerCase();
export function bytes(size) {
  if (!Number.isFinite(size) || size < 0) return "大小未知";
  if (size < 1024) return `${size} B`;
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 ** 2).toFixed(1)} MB`;
}
export function dateLabel(seconds) {
  if (!Number.isFinite(seconds)) return "时间未知";
  const date = new Date(seconds * 1000);
  if (!Number.isFinite(date.getTime())) return "时间未知";
  return `${String(date.getMonth()+1).padStart(2,"0")}/${String(date.getDate()).padStart(2,"0")} ${String(date.getHours()).padStart(2,"0")}:${String(date.getMinutes()).padStart(2,"0")}`;
}
export function filteredJobs(jobs, filter, query) {
  const needle = query.trim().toLocaleLowerCase();
  return jobs.filter(job => (filter !== "active" || active(job.state)) && (filter !== "attention" || attention(job.state)) &&
    (!needle || `${job.source?.filename || ""} ${job.id || ""} ${job.source_id || ""}`.toLocaleLowerCase().includes(needle)));
}
export const clipId = (value, size = 12) => {
  const text = String(value ?? "");
  if (!text || text.length <= size) return text;
  const edge = Math.max(3, Math.floor((size - 1) / 2));
  return `${text.slice(0, edge)}…${text.slice(-edge)}`;
};
export const diagnosticMessage = value => String(value ?? "")
  .replace(/Bearer\s+[^\s]+/gi, "Bearer [已隐藏]")
  .replace(/(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+/gi, "$1=[已隐藏]");
export function addDiagnostic(events, event, limit = 100) {
  const next = [...events, {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    at: Date.now(),
    kind: String(event?.kind || "info"),
    message: diagnosticMessage(event?.message || "未命名事件"),
    detail: diagnosticMessage(event?.detail || ""),
  }];
  return next.slice(-Math.max(1, limit));
}
export const eventTimeLabel = timestamp => {
  if (!Number.isFinite(timestamp)) return "时间未知";
  const date = new Date(timestamp);
  if (!Number.isFinite(date.getTime())) return "时间未知";
  return date.toLocaleTimeString("zh-CN", {hour12:false});
};
export const displayValue = value => typeof value === "string" ? value : JSON.stringify(value ?? null);
export const formatDescriptions = {
  txt: ["纯文本", "UTF-8 原文、字符位置与原始换行"],
  json: ["结构化数据", "保留原始数据类型与来源，拒绝重复键"],
  docx: ["Word 文档", "正文、表格、图片与可获取的文档附属内容"],
  pptx: ["演示文稿", "幻灯片正文、备注、表格与原生图表数据"],
  xlsx: ["Excel 工作簿", "单元格、公式、缓存、格式与工作表结构"],
  pdf: ["PDF 文档", "原生文字与页区域，明确标注未识别位图缺口"],
};
