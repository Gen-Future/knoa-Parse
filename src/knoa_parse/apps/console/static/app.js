import {states, active, attention, escapeHtml as esc, extension, bytes, dateLabel, filteredJobs, displayValue, formatDescriptions} from "./model.mjs";

const paths = {
  layers:'<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>',
  grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  settings:'<path d="M4 7h16M4 17h16"/><circle cx="8" cy="7" r="2.5"/><circle cx="16" cy="17" r="2.5"/>',
  book:'<path d="M12 6c-3-3-7-3-9-2v15c3-1 6-1 9 2 3-3 6-3 9-2V4c-2-1-6-1-9 2Zm0 0v15"/>',
  folder:'<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>',
  'chevron-down':'<path d="m8 10 4 4 4-4"/>', right:'<path d="m9 6 6 6-6 6"/>',
  refresh:'<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>', plus:'<path d="M12 5v14M5 12h14"/>',
  upload:'<path d="m7 8 5-5 5 5M12 3v12M4 15v5h16v-5"/>',
  fingerprint:'<path d="M5 12a7 7 0 0 1 14 0v3M8 13v-1a4 4 0 0 1 8 0v5M11 13v-1a1 1 0 0 1 2 0v4c0 3-1 5-3 6M5 15c0 3-1 4-2 5M8 16c0 3-1 5-2 6M16 20l1 2"/>',
  link:'<path d="m10 14 4-4M8 16l-2 2a4 4 0 0 1-5-5l4-4a4 4 0 0 1 6 0M16 8l2-2a4 4 0 0 1 5 5l-4 4a4 4 0 0 1-6 0" transform="translate(1 0) scale(.92)"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  file:'<path d="M13 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10L13 3Z"/><path d="M13 3v7h7M8 14h8M8 17h5"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>', 'arrow-right':'<path d="M4 12h16m-6-6 6 6-6 6"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  check:'<path d="m5 12 4 4L19 6"/>', alert:'<path d="m12 3 10 18H2L12 3ZM12 9v5m0 3v.1"/>',
  image:'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m21 16-6-6L4 21"/>',
  copy:'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.file}</svg>`;
document.querySelectorAll("[data-icon]").forEach(node => { node.innerHTML = icon(node.dataset.icon); });
const $ = id => document.getElementById(id);
const state = {connected:false, syncError:false, session:0, caps:null, jobs:[], hasMore:false, selected:null, external:null,
  results:new Map(), detailError:null, loadingResult:false, tab:"content", filter:"all", search:"", view:"workspace", blockLimit:20, lastSync:null, uploading:false};
const objectUrls = new Map();
let pollTimer, toastTimer, refreshPromise, selectionVersion = 0;

function toast(message, error = false) {
  $("toast").textContent = message;
  $("toast").className = `toast${error ? " error" : ""}`;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, error ? 8000 : 4000);
}
function announce(message) { $("announcer").textContent = message; }
function errorMessage(data, fallback) {
  return data?.error?.message || (typeof data?.detail === "string" ? data.detail : fallback);
}
async function request(path, {method="GET", body, raw=false, timeout=20000} = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const headers = {};
    if (body && !(body instanceof File)) headers["Content-Type"] = "application/json";
    const response = await fetch(`/api${path}`, {method, headers, body: body instanceof File ? body : body ? JSON.stringify(body) : undefined,
      credentials:"omit", cache:"no-store", signal:controller.signal});
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      const message = response.status === 401 ? "服务拒绝访问，请检查当前运行的服务版本。" : errorMessage(data, `请求未完成（HTTP ${response.status}）`);
      const error = new Error(message); error.status = response.status; throw error;
    }
    if (raw) return {blob:await response.blob(), type:response.headers.get("content-type")?.split(";")[0] || ""};
    return await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw new Error("服务响应超时。请检查实例是否正常运行，再手动重试。");
    if (error instanceof TypeError) throw new Error("无法连接解析实例。请检查服务是否已启动。");
    throw error;
  } finally { clearTimeout(timer); }
}
const badge = value => {
  const info = states[value] || {label:"未知状态", tone:"queued"};
  return `<span class="badge ${info.tone}">${info.label}</span>`;
};
function fileIcon(name) {
  const ext = extension(name);
  const known = Object.hasOwn(formatDescriptions, ext);
  return `<span class="file-icon ${known ? ext : ""}">${icon("file")}<small>${esc(ext.slice(0,5).toUpperCase())}</small></span>`;
}
function selectedJob() { return state.jobs.find(job => job.id === state.selected) || (state.external?.id === state.selected ? state.external : null); }
function resultFor(job) { return state.results.get(`${job.id}:${job.result_artifact_id}`); }
function showConnection() { connectWorkspace(); }
function renderConnection() {
  $("connection-status").innerHTML = `<span class="status-dot${state.syncError ? " error" : state.connected ? "" : " neutral"}"></span><span>${state.syncError ? "同步中断" : state.connected ? "实例已连接" : "服务未就绪"}</span>${icon("chevron-down")}`;
  $("schema-label").textContent = state.caps ? `SCHEMA ${state.caps.schema_version}` : "原生解析工作空间";
  $("last-synced").textContent = state.lastSync ? `更新于 ${new Date(state.lastSync).toLocaleTimeString("zh-CN", {hour12:false})}` : "正在加载本地服务";
  const formats = state.caps?.formats || [];
  $("format-chips").innerHTML = formats.length ? formats.map(f => `<span class="format-chip">${esc(f.extension.replace(/^\./,"").toUpperCase())}</span>`).join("") : '<span class="format-placeholder">连接后查看可用格式</span>';
  $("file-input").accept = formats.map(f => f.extension).join(",");
  $("live-label").textContent = state.syncError ? "同步中断" : state.connected ? "自动同步" : "未同步";
}
function renderJobs() {
  $("count-all").textContent = state.connected ? state.jobs.length : "—";
  $("count-active").textContent = state.connected ? state.jobs.filter(j => active(j.state)).length : "—";
  $("count-attention").textContent = state.connected ? state.jobs.filter(j => attention(j.state)).length : "—";
  $("count-scope").textContent = state.hasMore ? "最近 100 项" : "当前返回列表";
  const jobs = filteredJobs(state.jobs, state.filter, state.search);
  $("task-count").textContent = state.connected ? jobs.length : "0";
  $("list-scope").textContent = state.connected ? (state.hasMore ? "仅展示最近 100 项 · 更早任务可按 ID 打开" : `已读取 ${state.jobs.length} 项任务`) : "等待连接后读取任务";
  document.querySelectorAll("[data-filter]").forEach(button => { button.classList.toggle("active", button.dataset.filter === state.filter); button.setAttribute("aria-pressed", button.dataset.filter === state.filter); });
  if (!state.connected || !jobs.length) {
    const connected = state.connected;
    const searching = state.jobs.length > 0;
    $("task-list").innerHTML = `<div class="list-empty"><span class="empty-symbol">${icon(connected ? "search" : "link")}</span><h3>${connected ? searching ? "没有匹配的任务" : "从第一份资料开始" : "正在连接本地服务"}</h3><p>${connected ? searching ? "试试其他名称或状态；更早的记录可按完整任务 ID 打开。" : "提交一份资料，在这里观察它的状态、内容与出处。" : "服务启动后自动读取任务与证据，无需登录。"}</p>${!connected ? '<button class="button quiet" data-action="connect">重试连接</button>' : ""}</div>`;
    return;
  }
  $("task-list").innerHTML = `<div class="table-labels"><span>资料名称</span><span>任务状态</span><span class="date-label">创建时间</span><span></span></div>` + jobs.map(job => {
    const source = job.source || {};
    return `<button class="task-row${job.id === state.selected ? " selected" : ""}" data-job="${esc(job.id)}" aria-pressed="${job.id === state.selected}"><span class="file-cell">${fileIcon(source.filename)}<span class="file-info"><span class="filename">${esc(source.filename || job.source_id)}</span><span class="file-meta">${esc(bytes(source.size_bytes))} <span aria-hidden="true">·</span> ${esc(job.id.slice(0,8))}</span></span></span>${badge(job.state)}<span class="task-date">${esc(dateLabel(job.created_at))}</span>${icon("right")}</button>`;
  }).join("");
}
function renderCapabilities() {
  if (!state.connected) {
    $("capability-list").innerHTML = '<div class="list-empty"><span class="empty-symbol">'+icon("link")+'</span><h3>连接后查看当前能力</h3><p>这里不会预设实例已安装哪些解析组件。</p><button class="button quiet" data-action="connect">重试连接</button></div>';
    return;
  }
  const formats = state.caps.formats || [];
  $("capability-list").innerHTML = '<div class="capability-table"><div class="capability-row head"><span>资料格式</span><span>原生解析范围</span><span>可用状态</span></div>' + formats.map(format => {
    const ext = format.extension.replace(/^\./, "");
    const [label, description] = formatDescriptions[ext] || [format.extension, format.target];
    return `<div class="capability-row"><div class="file-cell">${fileIcon(`file.${ext}`)}<strong>${esc(label)}</strong></div><p>${esc(description)}</p><span class="badge succeeded">已启用</span></div>`;
  }).join("") + '</div>' + `<div class="capability-note"><strong>${state.caps.local_model_inference === false ? "本地模型推理关闭" : "请核对实例模型策略"}</strong><br>${state.caps.external_capabilities?.length ? `当前外部服务：${state.caps.external_capabilities.map(item => esc(typeof item === "string" ? item : `${item.provider} · ${item.protocol} · ${item.model}`)).join("；")}` : "外部模型服务尚未配置，可前往模型服务设置。"}</div>`;
}
function switchView(view) {
  state.view = view;
  $("workspace-view").hidden = view !== "workspace";
  $("capabilities-view").hidden = view !== "capabilities";
  $("models-view").hidden = view !== "models";
  const title = {workspace:"解析工作台",capabilities:"能力清单",models:"模型服务"}[view];
  $("page-title").innerHTML = `${title}<span class="heading-period">.</span>`;
  $("breadcrumb-page").textContent = title;
  $("page-subtitle").textContent = {workspace:"看见资料如何成为证据。",capabilities:"清楚了解当前实例的解析范围。",models:"选择平台渠道，连接适合你的模型。"}[view];
  $("new-parse").hidden = view !== "workspace";
  document.querySelectorAll("[data-view]").forEach(button => button.classList.toggle("active", button.dataset.view === view));
  if (view === "models") loadModelSettings();
}

let savedModelSettings = null, modelBusy = false, modelDirty = false, modelLoadVersion = 0;
function modelNotice(message, error=false) {
  $("model-settings-status").textContent = message;
  $("model-settings-status").className = `notice${error ? " error" : ""}`;
  $("model-settings-status").hidden = !message;
}
function modelControls() {
  $("model-auth-notice").hidden = state.connected;
  const writable = state.connected && savedModelSettings?.editable && !modelBusy;
  $("model-save").disabled = !writable;
  $("model-test").disabled = !state.connected || !savedModelSettings?.key_configured || modelBusy || modelDirty;
  $("model-reload").disabled = !state.connected || modelBusy;
  $("model-custom-name").hidden = $("model-platform").value !== "custom";
  $("model-protocol").disabled = $("model-platform").value === "siliconflow";
  $("model-thinking-field").hidden = $("model-protocol").value !== "openai";
}
function fillModelSettings(settings) {
  savedModelSettings = settings; modelDirty = false;
  $("model-platform").value = settings.provider === "siliconflow" ? "siliconflow" : "custom";
  $("model-provider-name").value = settings.provider === "siliconflow" ? "custom-platform" : settings.provider;
  $("model-protocol").value = settings.protocol;
  $("model-base-url").value = settings.base_url;
  $("model-name").value = settings.model;
  $("model-timeout").value = settings.timeout_seconds;
  $("model-thinking").value = settings.enable_thinking === null ? "default" : String(settings.enable_thinking);
  $("model-api-key").value = "";
  $("model-api-key").placeholder = settings.key_configured ? "已配置 · 留空保留当前渠道密钥" : "输入模型平台的 API Key";
  $("model-key-state").textContent = settings.key_configured ? "已配置，不回显" : "尚未配置";
  $("model-saved-summary").textContent = `${settings.key_configured ? "当前渠道" : "待配置"}：${settings.provider} · ${settings.protocol.toUpperCase()}\n${settings.model}\n${settings.base_url}`;
  modelControls();
}
async function loadModelSettings() {
  modelControls();
  if (!state.connected || modelBusy) return;
  const session=state.session, version=++modelLoadVersion;
  modelBusy=true; modelControls();
  try {
    const settings=await request("/v1/settings/model");
    if(session!==state.session || version!==modelLoadVersion)return;
    fillModelSettings(settings);
    modelNotice(settings.editable ? "" : "当前由模型环境变量覆盖，暂不可在界面保存。请先移除对应环境变量并重启。");
  } catch(error) { if(session===state.session)modelNotice(error.message,true); }
  finally { if(version===modelLoadVersion){modelBusy=false;modelControls();} }
}
$("model-platform").addEventListener("change",()=>{
  $("model-api-key").value="";
  if($("model-platform").value==="siliconflow") {
    $("model-protocol").value="openai"; $("model-base-url").value="https://api.siliconflow.cn/v1";
    $("model-name").value="deepseek-ai/DeepSeek-V3.2"; $("model-thinking").value="false";
  } else {
    $("model-base-url").value=""; $("model-name").value=""; $("model-thinking").value="default";
  }
  modelDirty=true;modelControls();modelNotice("渠道已修改，请填写对应设置并保存。");
});
$("model-protocol").addEventListener("change",()=>{ $("model-api-key").value="";modelDirty=true;modelControls(); });
$("model-settings-form").addEventListener("input",()=>{modelDirty=true;modelControls();modelNotice("有尚未保存的修改；保存后可测试连接。");});
$("model-settings-form").addEventListener("change",()=>{modelDirty=true;modelControls();});
$("model-reload").addEventListener("click",loadModelSettings);
$("model-settings-form").addEventListener("submit",async event=>{
  event.preventDefault();if(!state.connected){showConnection();return;}if(modelBusy)return;
  const session=state.session;
  const changes={provider:$("model-platform").value==="siliconflow"?"siliconflow":$("model-provider-name").value.trim(),
    protocol:$("model-protocol").value,base_url:$("model-base-url").value.trim(),model:$("model-name").value.trim(),
    timeout_seconds:Number($("model-timeout").value),
    enable_thinking:$("model-protocol").value==="anthropic"||$("model-thinking").value==="default"?null:$("model-thinking").value==="true"};
  const key=$("model-api-key").value.trim();if(key)changes.api_key=key;
  modelBusy=true;modelControls();modelNotice("正在保存模型服务配置…");
  try {
    const settings=await request("/v1/settings/model",{method:"PUT",body:changes});
    if(session!==state.session)return;
    fillModelSettings(settings);modelNotice("设置已保存并立即生效，可以测试连接。");
    state.caps=await request("/v1/capabilities");renderCapabilities();
  } catch(error) {if(session===state.session)modelNotice(error.message,true);}
  finally {if(session===state.session){modelBusy=false;modelControls();}}
});
$("model-test").addEventListener("click",async()=>{
  if(modelBusy||modelDirty)return;
  const session=state.session;modelBusy=true;modelControls();modelNotice("正在测试已保存渠道，请稍候…");
  try {
    const result=await request("/v1/settings/model/test",{method:"POST",timeout:Math.max(20000,(savedModelSettings.timeout_seconds+10)*1000)});
    if(session!==state.session)return;
    modelNotice(`连接成功 · ${result.provider} · ${result.model} · ${result.text}${result.usage.total_tokens===null?"":` · ${result.usage.total_tokens} tokens`}`);
  } catch(error) {if(session===state.session)modelNotice(error.message,true);}
  finally {if(session===state.session){modelBusy=false;modelControls();}}
});
function locatorLabel(location) {
  const precision = {source_exact:"原件精确定位", derived_exact:"派生结果定位", estimated:"估计位置", unavailable:"不可定位"}[location.precision] || location.precision;
  let position = "";
  if (location.kind === "text_span") position = `字符 ${location.start}–${location.end}`;
  if (location.kind === "sheet_range") position = `${location.sheet}!${location.a1_range}`;
  if (location.kind === "page_region") position = `第 ${location.page} 页 · ${location.unit} · ${location.origin === "top_left" ? "左上原点" : "左下原点"}`;
  if (location.kind === "document_node" || location.kind === "structured_node") position = location.pointer || "文档容器";
  return `${precision} · ${position}`;
}
function tableMarkup(data) {
  const rows = Math.min(Math.max(Number(data.rows) || 0,0), 15);
  const cols = Math.min(Math.max(Number(data.columns) || 0,0), 8);
  const cells = Array.isArray(data.cells) ? data.cells : [];
  const covered = new Set();
  let markup = "";
  for (let row=0; row<rows; row++) {
    markup += "<tr>";
    for (let col=0; col<cols; col++) {
      if (covered.has(`${row}:${col}`)) continue;
      const cell = cells.find(c => c.row === row && c.column === col);
      const rowSpan = Math.max(1,Math.min(Number(cell?.row_span) || 1,rows-row));
      const colSpan = Math.max(1,Math.min(Number(cell?.column_span) || 1,cols-col));
      for (let r=row;r<row+rowSpan;r++) for (let c=col;c<col+colSpan;c++) if (r!==row || c!==col) covered.add(`${r}:${c}`);
      const tag = cell?.column_header ? "th" : "td";
      markup += `<${tag} rowspan="${rowSpan}" colspan="${colSpan}">${esc(String(cell?.text ?? "").slice(0,4000))}</${tag}>`;
    }
    markup += "</tr>";
  }
  return `<div class="table-scroll"><table class="evidence-table"><tbody>${markup}</tbody></table></div>${data.rows>rows || data.columns>cols ? `<p class="table-note">显示前 ${rows} 行、${cols} 列。完整数据保留在原始结果中。</p>` : ""}`;
}
function blockMarkup(block, index) {
  const data = block.data || {};
  const label = data.role === "native_chart" ? "原生图表数据" : data.role === "original_cell" ? "原始单元格" : data.content_role === "notes" ? "演讲者备注" : ({title:"标题", section_header:"章节标题", text:"正文", paragraph:"段落", footnote:"脚注", page_header:"页眉", page_footer:"页脚", list_item:"列表项"}[data.label] || {text:"原生文字",table:"表格",image:"图片",structured:"结构化内容"}[block.kind] || block.kind);
  let content = "";
  if (block.kind === "text") content = `<p class="block-text${["title","section_header"].includes(data.label) ? " heading" : ""}">${esc((block.text || "").slice(0,12000))}</p>${block.text?.length>12000 ? '<p class="table-note">此处显示前 12,000 字符，完整内容见原始结果。</p>' : ""}`;
  else if (block.kind === "table") content = tableMarkup(data);
  else if (block.kind === "image") {
    const url = objectUrls.get(data.image_artifact_id);
    content = url ? `<img class="image-preview" src="${esc(url)}" alt="原件中提取的图片，未进行 OCR 或视觉理解">` : `<div class="image-placeholder"><span>${icon("image")} 原件中的图片</span>${data.image_artifact_id ? `<button class="text-button" data-load-image="${esc(data.image_artifact_id)}">加载图片 ${icon("right")}</button>` : '<span>无可用图片产物</span>'}</div>`;
  } else if (data.role === "original_cell") {
    content = `<dl class="data-grid"><dt>工作表 / 位置</dt><dd>${esc(data.sheet)} · <code>${esc(data.address)}</code></dd><dt>原始值</dt><dd>${esc(displayValue(data.raw_value))}</dd>${data.formula ? `<dt>公式</dt><dd><code>${esc(data.formula)}</code></dd><dt>计算缓存</dt><dd>${data.cache_state === "not_available" ? "原件未提供缓存" : esc(displayValue(data.cached_value))}</dd>` : ""}<dt>原生类型 / 格式</dt><dd>${esc(data.data_type)} · ${esc(data.number_format)}</dd>${data.row_hidden || data.column_hidden || data.sheet_state !== "visible" ? `<dt>隐藏状态</dt><dd>${[data.row_hidden?"隐藏行":"",data.column_hidden?"隐藏列":"",data.sheet_state!=="visible"?data.sheet_state:""].filter(Boolean).map(esc).join(" · ")}</dd>` : ""}</dl>`;
  } else content = `<pre class="raw-json">${esc(JSON.stringify(data,null,2).slice(0,12000))}</pre>`;
  const position = (block.locators || []).map(locatorLabel).join("\n");
  return `<article class="block"><div class="block-heading"><span><span class="block-number">${String(index+1).padStart(2,"0")}</span>${esc(label)}</span><span class="evidence-label">${block.acquisition === "native" ? "原生" : esc(block.acquisition)}</span></div>${content}<div class="locator">${esc(position)}</div></article>`;
}
const issueTitles = {external_ocr_required:"位图内容尚未识别", reading_order_unresolved:"阅读顺序尚未重建", derived_locations:"定位指向保留的派生结果", images_not_recognized:"图片已保留，尚未进行识别", chart_visual_not_rendered:"原生图表数据已保留，视觉未渲染", engine_incomplete:"转换未完整完成", image_unavailable:"图片产物不可用", no_native_content:"未找到原生文字或位图"};
function resultBody(job, result) {
  if (state.detailError) return `<div class="waiting-state">${icon("alert")}<h3>暂时无法读取结果</h3><p>${esc(state.detailError)}</p><button class="text-button" data-action="retry-result">重新读取</button></div>`;
  if (state.loadingResult) return '<div class="waiting-state"><span class="spinner"></span><h3>正在读取证据</h3><p>正在获取这份任务已发布的结果。</p></div>';
  if (!result) {
    const title = {queued:"等待 worker 执行",running:"解析正在进行",cancelled:"任务已取消",failed:"本次任务未生成结果"}[job.state] || "尚无可用结果";
    const message = job.error?.message || ({queued:"API 已接收任务。请确认独立 worker 使用相同的数据目录；控制台会同步任务状态。",running:"服务尚未返回结果。当前没有细分阶段与百分比信息。",cancelled:"已保留原件。如需重新解析，请显式创建新任务。"}[job.state] || "待服务发布结果后，这里会展示内容、覆盖情况和产物。");
    return `<div class="waiting-state"><span>${active(job.state) ? '<i class="spinner"></i>' : icon("file")}</span><h3>${title}</h3><p>${esc(message)}</p>${job.error?.code ? `<p><code>${esc(job.error.code)}</code></p>` : ""}</div>`;
  }
  if (state.tab === "content") return result.blocks.length ? result.blocks.slice(0,state.blockLimit).map(blockMarkup).join("") + (result.blocks.length>state.blockLimit ? `<div class="more-blocks"><button data-action="more-blocks">再显示 20 个内容块 · 共 ${result.blocks.length} 个</button></div>` : "") : '<div class="waiting-state"><h3>没有可展示的内容块</h3><p>请结合覆盖与问题判断，这是空内容还是明确的解析失败。</p></div>';
  if (state.tab === "issues") {
    return '<h3 class="detail-section-title">覆盖单元</h3>' + result.coverage.map(unit => `<div class="coverage-item"><code>${esc(unit.unit_id)}</code><span class="badge ${unit.status === "completed" ? "succeeded" : unit.status === "failed" ? "partial" : "queued"}">${{completed:"已完成",failed:"有缺口",skipped:"已跳过"}[unit.status] || esc(unit.status)}</span></div>`).join("") + '<h3 class="detail-section-title issues-title">问题与边界</h3>' + (result.issues.length ? result.issues.map(issue => `<article class="issue ${issue.severity === "error" ? "error" : ""}"><h4>${esc(issueTitles[issue.code] || issue.code)}</h4><p>${esc(issue.message)}</p><code>${esc(issue.code)}${issue.unit_id ? ` · ${esc(issue.unit_id)}` : ""}</code></article>`).join("") : '<p class="table-note">当前结果未报告问题。</p>');
  }
  const raw = JSON.stringify(result,null,2);
  return `<div class="artifact-list">${result.artifacts.map(artifact => `<div class="coverage-item"><span>${esc({source:"原始资料",engine_result:"上游完整结果",derived:"派生产物"}[artifact.role] || artifact.role)} · ${esc(bytes(artifact.size_bytes))}</span><button class="text-button" data-download-artifact="${esc(artifact.id)}">下载 ${icon("download")}</button></div>`).join("")}</div><p class="table-note">${esc(result.engine)} · ${esc(result.schema_version)}</p><pre class="raw-json">${esc(raw.slice(0,100000))}</pre>${raw.length>100000 ? '<p class="table-note">预览显示前 100,000 字符，可下载完整结果。</p>' : ""}`;
}
function renderInspector() {
  const previousKey = $("inspector-content").dataset.viewKey;
  const viewKey = `${state.selected}:${state.tab}`;
  const previousScroll = previousKey === viewKey ? document.querySelector(".detail-body")?.scrollTop || 0 : 0;
  $("inspector-content").dataset.viewKey = viewKey;
  const job = selectedJob();
  if (!job) {
    $("inspector-content").innerHTML = `<div class="inspector-empty"><span class="empty-symbol">${icon("layers")}</span><h2 id="inspector-title">从一份资料，看见全貌。</h2><p>选择左侧任务，检查解析内容、<br>来源位置，以及尚未完成的部分。</p><span class="micro-label">SOURCE → STRUCTURE → EVIDENCE</span></div>`;
    return;
  }
  const source = job.source || {};
  const result = resultFor(job);
  $("inspector-content").dataset.renderKey = `${job.id}:${job.state}:${job.result_artifact_id}:${state.tab}:${state.blockLimit}`;
  const returned = Boolean(job.result_artifact_id);
  const completed = !active(job.state);
  const summary = result ? ({completed:`已保留 ${result.blocks.length} 个内容块，来源可追溯。`,partial:"已保留可用证据，仍有需要关注的解析缺口。",failed:"结果明确报告失败，请查看问题与原件。"}[result.status]) : "";
  $("inspector-content").innerHTML = `<div class="detail-header"><div class="detail-topline"><span class="section-kicker mono">EVIDENCE INSPECTOR</span>${badge(job.state)}</div><div class="detail-title-line">${fileIcon(source.filename)}<div><h2 id="inspector-title">${esc(source.filename || job.source_id)}</h2><p>${esc(extension(source.filename).toUpperCase())} · ${esc(bytes(source.size_bytes))} · 原生提取</p></div></div><div class="detail-id">${esc(job.id)}<button data-copy-id="${esc(job.id)}" aria-label="复制任务 ID">${icon("copy")}</button></div></div><div class="task-track"><span class="track-step done"><i>✓</i>原件已接收</span><span class="track-join"></span><span class="track-step ${completed?"done":"active"}"><i>${completed?"✓":"2"}</i>${job.state === "queued" ? "等待执行" : job.state === "running" ? "正在解析" : job.state === "cancelled" ? "任务已取消" : "任务已返回"}</span><span class="track-join"></span><span class="track-step ${returned?"done":""}"><i>${returned?"✓":"3"}</i>${returned?"结果已发布":"结果未发布"}</span></div>${summary ? `<div class="result-summary ${result.status === "partial" ? "partial" : result.status === "failed" ? "failed" : ""}">${icon(result.status === "completed" ? "check" : "alert")}<span>${summary}</span></div>` : ""}<div class="detail-tabs" role="tablist" aria-label="结果视图">${[["content","内容",result?.blocks.length],["issues","覆盖与问题",result?.issues.length],["raw","原始结果",null]].map(([id,label,count])=>`<button role="tab" id="detail-tab-${id}" aria-controls="detail-panel" tabindex="${state.tab===id?0:-1}" aria-selected="${state.tab===id}" data-tab="${id}" class="${state.tab===id?"active":""}">${label}${Number.isFinite(count)?`<small>${count}</small>`:""}</button>`).join("")}</div><div class="detail-body" id="detail-panel" role="tabpanel" aria-labelledby="detail-tab-${state.tab}">${resultBody(job,result)}</div><div class="detail-actions"><button class="text-button" data-download-source="${esc(source.id || job.source_id)}">${icon("download")}下载原件</button>${active(job.state) ? `<button class="text-button" data-cancel="${esc(job.id)}">取消任务 ${icon("close")}</button>` : result ? `<button class="text-button" data-action="download-result">完整结果 JSON ${icon("download")}</button>` : ""}</div>`;
  const detailBody = document.querySelector(".detail-body");
  if (detailBody) detailBody.scrollTop = previousScroll;
}
async function loadSelection() {
  const job = selectedJob();
  const renderKey = job ? `${job.id}:${job.state}:${job.result_artifact_id}:${state.tab}:${state.blockLimit}` : "";
  if (job && resultFor(job) && !state.loadingResult && !state.detailError && $("inspector-content").dataset.renderKey === renderKey) return;
  const version = ++selectionVersion;
  state.detailError = null;
  if (!job?.result_artifact_id || resultFor(job)) { state.loadingResult=false; renderInspector(); return; }
  state.loadingResult = true; renderInspector();
  const session = state.session;
  try {
    const result = await request(`/v1/jobs/${encodeURIComponent(job.id)}/result`);
    if (session !== state.session) return;
    state.results.set(`${job.id}:${job.result_artifact_id}`,result);
    while (state.results.size > 6) state.results.delete(state.results.keys().next().value);
  } catch (error) { if (version === selectionVersion) state.detailError = error.message; }
  finally { if (version === selectionVersion && session === state.session) { state.loadingResult=false; renderInspector(); } }
}
function selectJob(id) {
  if (id !== state.selected) { objectUrls.forEach(url=>URL.revokeObjectURL(url)); objectUrls.clear(); }
  state.selected = id; state.tab = "content"; state.blockLimit = 20;
  history.replaceState(null,"",`#job=${encodeURIComponent(id)}`);
  renderJobs(); loadSelection();
}
function schedulePoll() {
  clearTimeout(pollTimer);
  if (!state.connected) return;
  const interval = state.jobs.some(job => active(job.state)) ? 2500 : 10000;
  pollTimer = setTimeout(() => { if (document.hidden) schedulePoll(); else refresh(); },interval);
}
async function refresh() {
  if (!state.connected) { showConnection(); return; }
  if (refreshPromise) return refreshPromise;
  const session = state.session;
  refreshPromise = (async () => {
    $("refresh").disabled = true;
    try {
      const listing = await request("/v1/jobs?limit=100");
      if (session !== state.session) return;
      state.jobs = listing.items; state.hasMore = listing.has_more;
      if (state.external?.id === state.selected && !state.jobs.some(job => job.id === state.selected)) state.external = {...state.external,...await request(`/v1/jobs/${encodeURIComponent(state.selected)}`)};
      state.lastSync = Date.now(); state.syncError=false; $("global-error").hidden = true;
      if (!state.selected && state.jobs.length) state.selected = state.jobs[0].id;
      renderConnection(); renderJobs(); await loadSelection();
    } catch (error) {
      if (session !== state.session) return;
      $("global-error").textContent = `${error.message} 当前显示的是上次成功同步的记录。`;
      state.syncError=true; $("global-error").hidden = false; renderConnection();
      
    } finally { $("refresh").disabled = false; refreshPromise = null; schedulePoll(); }
  })();
  return refreshPromise;
}
async function openJob(id) {
  if (!state.connected) { showConnection(); return; }
  const session = state.session;
  const job = await request(`/v1/jobs/${encodeURIComponent(id)}`);
  const source = await request(`/v1/sources/${encodeURIComponent(job.source_id)}`);
  if (session !== state.session) return;
  state.external = {...job,source}; switchView("workspace"); selectJob(id);
}
function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a"); link.href=url; link.download=name; link.click();
  setTimeout(()=>URL.revokeObjectURL(url),10000);
}
async function downloadArtifact(id) {
  const source = selectedJob()?.source;
  const {blob} = await request(`/v1/artifacts/${encodeURIComponent(id)}`,{raw:true});
  const suffix = {"image/png":"png","image/jpeg":"jpg","image/gif":"gif","image/webp":"webp","application/json":"json","application/pdf":"pdf","text/plain":"txt"}[blob.type.split(";")[0]] || "bin";
  const name = id === source?.id ? source.filename : `${id}.${suffix}`;
  saveBlob(blob,name); toast("产物已准备下载。");
}
async function upload(files) {
  if (!state.connected) { showConnection(); toast("请先连接工作空间，再选择资料。"); return; }
  if (state.uploading || !files.length) return;
  if (files.length>20) { toast("每批最多选择 20 个文件，请分批提交。",true); return; }
  const formats = new Set(state.caps.formats.map(format=>format.extension.toLowerCase()));
  const invalid = files.find(file => !formats.has(`.${extension(file.name)}`));
  if (invalid) { toast(`当前实例尚未启用 ${extension(invalid.name).toUpperCase()} 格式。`,true); return; }
  state.uploading = true; $("choose-file").disabled = true; $("new-parse").disabled = true;
  $("upload-state").hidden = false;
  const session = state.session;
  let submitted = 0, lastId = null;
  try {
    for (const [index,file] of files.entries()) {
      if (session !== state.session) break;
      $("upload-state").textContent = `正在提交 ${index+1} / ${files.length}：${file.name}`;
      const source = await request(`/v1/sources?filename=${encodeURIComponent(file.name)}`,{method:"POST",body:file});
      if (session !== state.session) break;
      let job;
      try { job = await request("/v1/jobs",{method:"POST",body:{source_id:source.id,idempotency_key:crypto.randomUUID()}}); }
      catch(error) { throw new Error(`原件已上传，但任务创建未确认。来源 ID：${source.id}。${error.message}`); }
      submitted++; lastId=job.id;
    }
    if (session === state.session) {
      await refresh(); if (lastId) selectJob(lastId);
      toast(`已提交 ${submitted} 项任务，等待 worker 执行。`); announce(`已提交 ${submitted} 项解析任务`);
    }
  } catch(error) { toast(`${submitted ? `已成功提交 ${submitted} 项。` : ""}${error.message}`,true); await refresh(); }
  finally { state.uploading=false; $("upload-state").hidden=true; $("choose-file").disabled=false; $("new-parse").disabled=false; $("file-input").value=""; }
}
function resetWorkspace() {
  modelLoadVersion++;savedModelSettings=null;modelBusy=false;modelDirty=false;
  $("model-api-key").value="";$("model-key-state").textContent="尚未读取";
  $("model-saved-summary").textContent="服务就绪后显示当前已保存的渠道。";modelNotice("");
  state.session++; state.connected=false; state.syncError=false; state.caps=null; state.jobs=[]; state.hasMore=false; state.external=null; state.selected=null;
  state.results.clear(); state.lastSync=null; state.detailError=null; state.loadingResult=false;
  clearTimeout(pollTimer); selectionVersion++;
  objectUrls.forEach(url=>URL.revokeObjectURL(url)); objectUrls.clear();
  $("global-error").hidden=true;
  renderConnection();renderJobs();renderInspector();renderCapabilities();
  modelControls();
}

let connecting = false;
async function connectWorkspace() {
  if (connecting) return;
  connecting = true;
  try {
    const [caps, listing] = await Promise.all([request("/v1/capabilities"),request("/v1/jobs?limit=100")]);
    resetWorkspace(); state.connected=true; state.caps=caps; state.jobs=listing.items; state.hasMore=listing.has_more; state.lastSync=Date.now();
    const hashId = new URLSearchParams(location.hash.slice(1)).get("job");
    state.selected=state.jobs.find(job=>job.id===hashId)?.id || state.jobs[0]?.id || null;
    renderConnection();renderJobs();renderCapabilities();loadSelection();schedulePoll();
    if(state.view==="models")loadModelSettings();
    if(hashId && hashId!==state.selected)openJob(hashId).catch(()=>toast("链接中的任务未找到，已显示最近记录。",true));
  } catch(error) {
    $("global-error").textContent=error.message;
    $("global-error").hidden=false;
    state.syncError=true;renderConnection();
    modelNotice(error.message,true);
  } finally { connecting=false; }
}
$("connection-status").addEventListener("click",showConnection);
$("connection-nav").addEventListener("click",showConnection);
$("refresh").addEventListener("click",()=>refresh());
$("new-parse").addEventListener("click",()=>state.connected?$("file-input").click():showConnection());
$("choose-file").addEventListener("click",()=>state.connected?$("file-input").click():showConnection());
$("file-input").addEventListener("change",event=>upload([...event.target.files]));
$("search").addEventListener("input",event=>{state.search=event.target.value;renderJobs();});
$("import-job").addEventListener("click",()=>{if(!state.connected){showConnection();return;}$("job-error").hidden=true;$("job-dialog").showModal();$("job-id-input").focus();});
$("job-form").addEventListener("submit",async event=>{event.preventDefault();const button=event.target.querySelector('[type="submit"]');button.disabled=true;try{await openJob($("job-id-input").value.trim());$("job-dialog").close();}catch(error){$("job-error").textContent=error.message;$("job-error").hidden=false;}finally{button.disabled=false;}});
for (const name of ["dragenter","dragover"]) $("drop-zone").addEventListener(name,event=>{event.preventDefault();$("drop-zone").classList.add("dragover");});
$("drop-zone").addEventListener("dragleave",event=>{if(!$("drop-zone").contains(event.relatedTarget))$("drop-zone").classList.remove("dragover");});
$("drop-zone").addEventListener("drop",event=>{event.preventDefault();$("drop-zone").classList.remove("dragover");upload([...event.dataTransfer.files]);});
window.addEventListener("dragover",event=>event.preventDefault());
window.addEventListener("drop",event=>event.preventDefault());
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&state.connected)refresh();});
document.addEventListener("keydown",event=>{
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="k"&&!document.querySelector("dialog[open]")){event.preventDefault();switchView("workspace");$("search").focus();}
  if(event.target.matches('[role="tab"]') && ["ArrowLeft","ArrowRight","Home","End"].includes(event.key)){
    event.preventDefault(); const tabs=[...document.querySelectorAll('[role="tab"]')]; const index=tabs.indexOf(event.target);
    const next=event.key==="Home"?0:event.key==="End"?tabs.length-1:(index+(event.key==="ArrowRight"?1:tabs.length-1))%tabs.length;
    const target=tabs[next].dataset.tab; tabs[next].click(); document.querySelector(`[data-tab="${target}"]`).focus();
  }
});
document.addEventListener("click",async event=>{
  const button=event.target.closest("button"); if(!button) return;
  try {
    if(button.classList.contains("close-dialog"))button.closest("dialog").close();
    if(button.dataset.view)switchView(button.dataset.view);
    if(button.dataset.filter){state.filter=button.dataset.filter;renderJobs();}
    if(button.dataset.job)selectJob(button.dataset.job);
    if(button.dataset.tab){state.tab=button.dataset.tab;renderInspector();}
    if(button.dataset.action==="connect")showConnection();
    if(button.dataset.action==="retry-result")loadSelection();
    if(button.dataset.action==="more-blocks"){state.blockLimit+=20;const body=document.querySelector(".detail-body");const top=body?.scrollTop||0;renderInspector();document.querySelector(".detail-body").scrollTop=top;}
    if(button.dataset.action==="download-result"){const job=selectedJob();const result=job&&resultFor(job);if(result)saveBlob(new Blob([JSON.stringify(result,null,2)],{type:"application/json"}),`knoa-${job.id}.json`);}
    if(button.dataset.downloadSource||button.dataset.downloadArtifact){button.disabled=true;try{await downloadArtifact(button.dataset.downloadSource||button.dataset.downloadArtifact);}finally{button.disabled=false;}}
    if(button.dataset.copyId){await navigator.clipboard.writeText(button.dataset.copyId);toast("已复制任务 ID。");}
    if(button.dataset.cancel){button.disabled=true;await request(`/v1/jobs/${encodeURIComponent(button.dataset.cancel)}/cancel`,{method:"POST"});await refresh();toast("取消请求已提交。");}
    if(button.dataset.loadImage){
      button.disabled=true;const session=state.session;
      try{const {blob,type}=await request(`/v1/artifacts/${encodeURIComponent(button.dataset.loadImage)}`,{raw:true});
        if(!["image/png","image/jpeg","image/gif","image/webp"].includes(type))throw new Error("此类型不提供内嵌预览，请从原始结果下载产物。");
        if(session!==state.session)return;
        const previous=objectUrls.get(button.dataset.loadImage);if(previous)URL.revokeObjectURL(previous);
        objectUrls.set(button.dataset.loadImage,URL.createObjectURL(blob));renderInspector();
      }finally{button.disabled=false;}
    }
  }catch(error){button.disabled=false;toast(error.message,true);}
});
renderConnection();renderJobs();renderInspector();renderCapabilities();

connectWorkspace();
