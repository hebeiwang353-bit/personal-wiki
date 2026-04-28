// MemoryOS Web UI 前端逻辑

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let currentPage = null;
let isEditing = false;
let originalContent = "";
let scanLogTimer = null;

// ── 初始化 ──────────────────────────────────────────────────
async function init() {
  await refreshStatus();
  await loadPages();
  bindEvents();
}

// ── 状态栏 ──────────────────────────────────────────────────
async function refreshStatus() {
  const r = await fetch("/api/status").then((r) => r.json());
  $("#stat-pages").textContent = r.page_count;
  $("#stat-tokens").textContent = r.context_tokens;
  $("#stat-schedule").textContent = r.schedule;

  if (r.summary) {
    $("#welcome-summary").textContent = r.summary;
  }
  renderRecentLogs(r.recent_logs);
}

function renderRecentLogs(text) {
  if (!text) return;
  const lines = text.split("\n").filter(Boolean);
  const html =
    `<h4>最近操作</h4><ul>` +
    lines.map((l) => `<li>${escapeHtml(l)}</li>`).join("") +
    `</ul>`;
  $("#recent-logs").innerHTML = html;
}

// ── 页面树 ──────────────────────────────────────────────────
async function loadPages() {
  const tree = await fetch("/api/pages").then((r) => r.json());
  fillNav("#nav-core", tree.core);
  fillNav("#nav-projects", tree.projects);
  fillNav("#nav-interests", tree.interests);
  fillNav("#nav-tools", tree.tools);
}

function fillNav(selector, items) {
  const ul = $(selector);
  ul.innerHTML = "";
  items.forEach((path) => {
    const li = document.createElement("li");
    li.textContent = displayName(path);
    li.dataset.path = path;
    li.addEventListener("click", () => openPage(path));
    ul.appendChild(li);
  });
}

function displayName(path) {
  const file = path.split("/").pop().replace(/\.md$/, "");
  return file;
}

// ── 打开页面 ────────────────────────────────────────────────
async function openPage(path) {
  if (isEditing && !confirm("正在编辑，要切换页面吗？未保存的修改会丢失。")) {
    return;
  }
  isEditing = false;
  currentPage = path;

  // 标记 active
  $$("#sidebar li").forEach((li) => li.classList.remove("active"));
  $$(`#sidebar li[data-path="${path}"]`).forEach((li) =>
    li.classList.add("active")
  );

  // 切换视图
  $("#welcome").classList.add("hidden");
  $("#editor").classList.remove("hidden");

  const r = await fetch(`/api/page/${encodeURIComponent(path)}`).then((r) =>
    r.json()
  );
  originalContent = r.content;
  $("#editor-path").textContent = path;
  renderPreview(originalContent);
  $("#textarea").value = originalContent;
  switchToPreview();
}

function renderPreview(md) {
  $("#preview").innerHTML = marked.parse(md);
}

// ── 编辑模式切换 ────────────────────────────────────────────
function switchToEdit() {
  isEditing = true;
  $("#preview").classList.add("hidden");
  $("#textarea").classList.remove("hidden");
  $("#btn-toggle-mode").classList.add("hidden");
  $("#btn-save").classList.remove("hidden");
  $("#btn-cancel").classList.remove("hidden");
  $("#textarea").focus();
}

function switchToPreview() {
  isEditing = false;
  $("#preview").classList.remove("hidden");
  $("#textarea").classList.add("hidden");
  $("#btn-toggle-mode").classList.remove("hidden");
  $("#btn-save").classList.add("hidden");
  $("#btn-cancel").classList.add("hidden");
}

// ── 保存 ────────────────────────────────────────────────────
async function savePage() {
  if (!currentPage) return;
  const content = $("#textarea").value;
  const r = await fetch(`/api/page/${encodeURIComponent(currentPage)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (r.ok) {
    originalContent = content;
    renderPreview(content);
    switchToPreview();
    toast("✓ 已保存");
    await refreshStatus();
  } else {
    toast("保存失败");
  }
}

function cancelEdit() {
  $("#textarea").value = originalContent;
  switchToPreview();
}

// ── 立即扫描 ────────────────────────────────────────────────
async function startScan() {
  if (!confirm("立即开始扫描？后台运行约 1-3 分钟，过程中可继续使用。")) return;
  const r = await fetch("/api/scan?max_files=500", { method: "POST" }).then(
    (r) => r.json()
  );
  if (r.ok) {
    toast(`✓ 扫描已启动（PID ${r.pid}）`);
    showScanLog();
  }
}

function showScanLog() {
  $("#modal-scan-log").classList.remove("hidden");
  pollScanLog();
  scanLogTimer = setInterval(pollScanLog, 2000);
}

async function pollScanLog() {
  const r = await fetch("/api/scan/log?lines=80").then((r) => r.json());
  $("#scan-log-content").textContent = r.lines.join("\n");
  // 自动滚到底
  const el = $("#scan-log-content");
  el.scrollTop = el.scrollHeight;
}

function closeScanLog() {
  $("#modal-scan-log").classList.add("hidden");
  if (scanLogTimer) {
    clearInterval(scanLogTimer);
    scanLogTimer = null;
  }
  refreshStatus();
  loadPages();
}

// ── 定时设定 ────────────────────────────────────────────────
function showSchedule() {
  $("#modal-schedule").classList.remove("hidden");
}
function hideSchedule() {
  $("#modal-schedule").classList.add("hidden");
}

async function confirmSchedule() {
  const time = $("#schedule-time").value;
  const r = await fetch("/api/schedule", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ time }),
  }).then((r) => r.json());
  if (r.ok) {
    toast(`✓ 定时已设：每天 ${time}`);
    hideSchedule();
    refreshStatus();
  } else {
    toast("设定失败");
  }
}

// ── 工具 ────────────────────────────────────────────────────
function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 2500);
}

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function bindEvents() {
  $("#btn-toggle-mode").addEventListener("click", switchToEdit);
  $("#btn-save").addEventListener("click", savePage);
  $("#btn-cancel").addEventListener("click", cancelEdit);
  $("#btn-scan").addEventListener("click", startScan);
  $("#btn-schedule").addEventListener("click", showSchedule);
  $("#schedule-cancel").addEventListener("click", hideSchedule);
  $("#schedule-confirm").addEventListener("click", confirmSchedule);
  $("#scan-log-close").addEventListener("click", closeScanLog);

  // Cmd/Ctrl+S 保存
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "s" && isEditing) {
      e.preventDefault();
      savePage();
    }
  });
}

init();
