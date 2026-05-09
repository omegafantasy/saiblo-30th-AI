function pct(v) {
  return `${(v * 100).toFixed(1)}%`;
}

function esc(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function attrEsc(s) {
  return esc(s).replaceAll('"', "&quot;");
}

function saibloMatchUrl(matchId) {
  return `https://www.saiblo.net/match/${encodeURIComponent(String(matchId))}`;
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
}

function shortCode(s) {
  const v = String(s || "");
  return v.length > 12 ? `${v.slice(0, 8)}...${v.slice(-4)}` : v;
}

function fmtScore(v, digits = 1) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "-";
  return Number.isInteger(n) ? String(n) : n.toFixed(digits);
}

function storageGet(key) {
  try {
    return window.localStorage.getItem(key) || "";
  } catch (e) {
    return "";
  }
}

function storageSet(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (e) {
    // localStorage may be disabled.
  }
}

const BOARD_PAGES = [
  {
    key: "game1",
    hash: "#game1",
    title: "Game1 Elo",
    panelId: "panel-saiblo-game1",
  },
  {
    key: "game53",
    hash: "#game53",
    title: "Game53 DeepClue 平均分",
    panelId: "panel-saiblo-game53",
  },
];

function boardIndexByKey(key) {
  return BOARD_PAGES.findIndex((page) => page.key === key);
}

function readSavedBoardKey() {
  return storageGet("saiblo-dashboard-board");
}

function saveBoardKey(key) {
  storageSet("saiblo-dashboard-board", key);
}

function initialBoardIndex() {
  const hashKey = String(window.location.hash || "").replace(/^#/, "");
  const hashIndex = boardIndexByKey(hashKey);
  if (hashIndex >= 0) return hashIndex;
  const savedIndex = boardIndexByKey(readSavedBoardKey());
  return savedIndex >= 0 ? savedIndex : 0;
}

let activeBoardIndex = initialBoardIndex();
let foldByUser = storageGet("saiblo-dashboard-fold-by-user") !== "0";
let latestPayload = null;

function setActiveBoard(index, options = {}) {
  const next = ((index % BOARD_PAGES.length) + BOARD_PAGES.length) % BOARD_PAGES.length;
  activeBoardIndex = next;
  const current = BOARD_PAGES[next];
  for (const [i, page] of BOARD_PAGES.entries()) {
    const panel = document.getElementById(page.panelId);
    if (panel) panel.hidden = i !== next;
  }
  const label = document.getElementById("boardCurrent");
  if (label) label.textContent = current.title;
  saveBoardKey(current.key);
  if (options.updateHash && window.location.hash !== current.hash) {
    window.history.replaceState(null, "", current.hash);
  }
}

function bindBoardSwitcher() {
  document.getElementById("boardPrev")?.addEventListener("click", () => {
    setActiveBoard(activeBoardIndex - 1, { updateHash: true });
  });
  document.getElementById("boardNext")?.addEventListener("click", () => {
    setActiveBoard(activeBoardIndex + 1, { updateHash: true });
  });
  window.addEventListener("hashchange", () => {
    setActiveBoard(initialBoardIndex(), { updateHash: false });
  });
}

function userFoldKey(row) {
  const username = String(row?.username || "").trim().toLowerCase();
  if (username) return `user:${username}`;
  return `code:${String(row?.code_id || row?.rank || Math.random()).trim().toLowerCase()}`;
}

function foldRowsByUser(rows) {
  if (!foldByUser) return rows || [];
  const seen = new Set();
  const out = [];
  for (const row of rows || []) {
    const key = userFoldKey(row);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(row);
  }
  return out;
}

function setFoldByUser(enabled) {
  foldByUser = Boolean(enabled);
  storageSet("saiblo-dashboard-fold-by-user", foldByUser ? "1" : "0");
  const input = document.getElementById("foldByUser");
  if (input) input.checked = foldByUser;
  renderBoards(latestPayload);
}

function bindFoldToggle() {
  const input = document.getElementById("foldByUser");
  if (!input) return;
  input.checked = foldByUser;
  input.addEventListener("change", () => setFoldByUser(input.checked));
}

function foldSummary(rawRows, displayRows) {
  if (!foldByUser) return "";
  const raw = Array.isArray(rawRows) ? rawRows.length : 0;
  const shown = Array.isArray(displayRows) ? displayRows.length : 0;
  if (raw <= 0 || shown === raw) return "";
  return `显示用户: <b>${shown}</b> / 版本: <b>${raw}</b>`;
}

function renderSaibloSummary(nodeId, v) {
  const node = document.getElementById(nodeId);
  if (!v || !v.available) {
    node.innerHTML = `<span class="err">数据不可用: ${esc(v?.error || "unknown")}</span>`;
    return;
  }
  const statusClass = v.status === "ok" ? "ok" : v.status === "auth_error" || v.status === "error" ? "err" : "warn";
  const parts = [
    `status: <b class="${statusClass}">${esc(v.status || "-")}</b>`,
    `Game: <b>${v.game_id}</b>`,
    `from #<b>${v.start_match_id}</b>`,
    `已记录: <b>${v.stored}</b>`,
    `成功: <b>${v.success}</b>`,
    `含回放元信息: <b>${v.success_with_replay_meta}</b>`,
    `Elo对局: <b>${v.matches_used}</b>`,
    `AI版本: <b>${v.rated_versions}</b>`,
    `跨版本: <b>${v.cross_rated_versions ?? "-"}</b>`,
    `默认: <b>${v.default_versions ?? "-"}</b>`,
    `pending: <b>${v.pending}</b>`,
    `failed: <b>${v.failed}</b>`,
    `范围: <b>${v.min_match_id || "-"} - ${v.max_match_id || "-"}</b>`,
    `文件时间(UTC): <b>${esc(v.file_mtime || "-")}</b>`,
  ];
  if (v.pending_source === "remote_state_scan" && Number(v.local_pending || 0) !== Number(v.pending || 0)) {
    parts.push(`本地待复查: <b>${v.local_pending}</b>`);
  }
  const displayRows = foldRowsByUser(v.rows || []);
  const folded = foldSummary(v.rows || [], displayRows);
  if (folded) {
    parts.push(folded);
  }
  if (v.status_message) {
    parts.push(`<span class="err">${esc(v.status_message)}</span>`);
  }
  node.innerHTML = parts.join(" | ");
}

function renderGame53Summary(nodeId, v) {
  const node = document.getElementById(nodeId);
  if (!v || !v.available) {
    node.innerHTML = `<span class="err">数据不可用: ${esc(v?.error || "unknown")}</span>`;
    return;
  }
  const statusClass = v.status === "ok" ? "ok" : v.status === "auth_error" || v.status === "error" ? "err" : "warn";
  const start = Number(v.start_match_id || 0) > 0 ? `from #<b>${v.start_match_id}</b>` : "from: <b>all</b>";
  const parts = [
    `status: <b class="${statusClass}">${esc(v.status || "-")}</b>`,
    `Game: <b>${v.game_id}</b>`,
    start,
    `已记录: <b>${v.stored}</b>`,
    `成功: <b>${v.success}</b>`,
    `有效分数: <b>${v.success_with_score}</b>`,
    `缺分/缺code: <b>${v.success_missing_score ?? "-"}</b>`,
    `计分样本: <b>${v.matches_used}</b>`,
    `AI版本: <b>${v.scored_versions}</b>`,
    `pending: <b>${v.pending}</b>`,
    `failed: <b>${v.failed}</b>`,
    `范围: <b>${v.min_match_id || "-"} - ${v.max_match_id || "-"}</b>`,
    `文件时间(UTC): <b>${esc(v.file_mtime || "-")}</b>`,
  ];
  const displayRows = foldRowsByUser(v.rows || []);
  const folded = foldSummary(v.rows || [], displayRows);
  if (folded) {
    parts.push(folded);
  }
  if (v.status_message) {
    parts.push(`<span class="err">${esc(v.status_message)}</span>`);
  }
  node.innerHTML = parts.join(" | ");
}

function renderSaibloTable(tableId, rows) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  if (!tbody) return;
  tbody.innerHTML = "";
  for (const r of rows || []) {
    const tr = document.createElement("tr");
    if (r.rank === 1) tr.className = "top1";
    const aiName = `${esc(r.username || "-")} / ${esc(r.entity || "-")} v${esc(r.version ?? "-")}`;
    const ladder = r.ladder_rank ? `#${r.ladder_rank} ${esc(r.ladder_score ?? "")}` : "-";
    const lastMatchId = Number(r.last_match_id || 0);
    const matchLink = lastMatchId > 0 ? saibloMatchUrl(lastMatchId) : "";
    const tags = [];
    if (r.provisional) tags.push('<span class="tag">少量</span>');
    if (r.rating_source === "default_self_play") tags.push('<span class="tag">自战默认</span>');
    else if (r.rating_source === "default_excluded") tags.push('<span class="tag">补局排除</span>');
    else if (r.rating_source === "default") tags.push('<span class="tag">默认</span>');
    if (r.self_play_games) tags.push(`<span class="tag">自战${r.self_play_games}</span>`);
    tr.innerHTML = `
      <td>${r.rank}</td>
      <td>
        <div class="main-cell">${aiName}${tags.length ? " " + tags.join(" ") : ""}</div>
        <div class="sub-cell">${esc(r.remark || "")}</div>
      </td>
      <td><code title="${esc(r.code_id)}">${esc(shortCode(r.code_id))}</code></td>
      <td>${Number(r.elo).toFixed(2)}</td>
      <td>${Number(r.raw_elo).toFixed(2)}</td>
      <td>${pct(r.reliability)}</td>
      <td>${r.games}</td>
      <td>${r.wins}-${r.losses}-${r.draws}</td>
      <td>${pct(r.win_rate)}</td>
      <td>${pct(r.score_rate)}</td>
      <td>${Number(r.avg_hp_diff).toFixed(2)}</td>
      <td>${Number(r.avg_rounds).toFixed(1)}</td>
      <td>${ladder}</td>
      <td>${r.last_match_id || "-"}</td>
      <td>
        <div class="row-actions">
          <button type="button" class="action-btn copy-token" data-token="${attrEsc(r.code_id)}" title="复制完整 code_id">复制</button>
          ${
            matchLink
              ? `<a class="action-btn" href="${attrEsc(matchLink)}" target="_blank" rel="noopener noreferrer" title="打开最近一轮对局">对局</a>`
              : '<button type="button" class="action-btn" disabled title="暂无最近对局">对局</button>'
          }
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

function renderGame53Table(tableId, rows) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  if (!tbody) return;
  tbody.innerHTML = "";
  for (const r of rows || []) {
    const tr = document.createElement("tr");
    if (r.rank === 1) tr.className = "top1";
    const aiName = `${esc(r.username || "-")} / ${esc(r.entity || "-")} v${esc(r.version ?? "-")}`;
    const lastMatchId = Number(r.last_match_id || 0);
    const bestMatchId = Number(r.best_match_id || 0);
    const matchLink = lastMatchId > 0 ? saibloMatchUrl(lastMatchId) : "";
    const tags = [];
    if (r.provisional) tags.push('<span class="tag">少量</span>');
    tr.innerHTML = `
      <td>${r.rank}</td>
      <td>
        <div class="main-cell">${aiName}${tags.length ? " " + tags.join(" ") : ""}</div>
        <div class="sub-cell">${esc(r.remark || "")}</div>
      </td>
      <td><code title="${attrEsc(r.code_id)}">${esc(shortCode(r.code_id))}</code></td>
      <td>${fmtScore(r.avg_score, 2)}</td>
      <td>${fmtScore(r.best_score, 1)}</td>
      <td>${fmtScore(r.min_score, 1)}</td>
      <td>${fmtScore(r.stddev_score, 2)}</td>
      <td>${r.games}</td>
      <td>${pct(r.reliability)}</td>
      <td>${fmtScore(r.last_score, 1)}</td>
      <td>${bestMatchId || "-"}</td>
      <td>${lastMatchId || "-"}</td>
      <td>
        <div class="row-actions">
          <button type="button" class="action-btn copy-token" data-token="${attrEsc(r.code_id)}" title="复制完整 code_id">复制</button>
          ${
            matchLink
              ? `<a class="action-btn" href="${attrEsc(matchLink)}" target="_blank" rel="noopener noreferrer" title="打开最近一轮对局">对局</a>`
              : '<button type="button" class="action-btn" disabled title="暂无最近对局">对局</button>'
          }
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

document.addEventListener("click", async (e) => {
  const btn = e.target.closest(".copy-token");
  if (!btn) return;
  const token = btn.dataset.token || "";
  if (!token) return;
  const old = btn.textContent;
  try {
    await copyText(token);
    btn.textContent = "已复制";
    btn.classList.add("copied");
  } catch (err) {
    btn.textContent = "失败";
    btn.classList.add("copy-failed");
  }
  window.setTimeout(() => {
    btn.textContent = old || "复制";
    btn.classList.remove("copied", "copy-failed");
  }, 1200);
});

function renderBoards(data) {
  if (!data) return;
  const game1 = data.views?.saiblo_game1;
  const game53 = data.views?.saiblo_game53;
  renderSaibloSummary("summary-saiblo-game1", game1);
  renderGame53Summary("summary-saiblo-game53", game53);
  renderSaibloTable("table-saiblo-game1", foldRowsByUser(game1?.rows || []));
  renderGame53Table("table-saiblo-game53", foldRowsByUser(game53?.rows || []));
  setActiveBoard(activeBoardIndex, { updateHash: false });
}

async function reload() {
  try {
    const res = await fetch(`/api/elo?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    latestPayload = data;
    document.getElementById("host").textContent = `host: ${data.hostname || "-"}`;
    document.getElementById("generatedAt").textContent = `更新时间: ${data.generated_at || "-"}`;
    renderBoards(data);
  } catch (e) {
    document.getElementById("generatedAt").innerHTML = `<span class="err">加载失败: ${esc(e.message)}</span>`;
  }
}

bindBoardSwitcher();
bindFoldToggle();
setActiveBoard(activeBoardIndex, { updateHash: false });
reload();
setInterval(reload, 15000);
