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

function renderSummary(nodeId, v) {
  const node = document.getElementById(nodeId);
  if (!v || !v.available) {
    node.innerHTML = `<span class="err">数据不可用: ${esc(v?.error || "unknown")}</span>`;
    return;
  }
  const parts = [
    `tag: <b>${esc(v.tag || "-")}</b>`,
    `总对局: <b>${v.matches}</b>`,
    `gpp: <b>${v.games_per_pair}</b>`,
    `mode: <b>${esc(v.mode || "-")}</b>`,
    `champion: <b>${esc(v.champion_old || "-")} -> ${esc(v.champion_new || "-")}</b>`,
    `promoted: <b>${v.champion_promoted ? "yes" : "no"}</b>`,
    `文件时间(UTC): <b>${esc(v.file_mtime || "-")}</b>`,
  ];
  if (typeof v.round_files === "number") {
    parts.splice(2, 0, `累计轮次文件: <b>${v.round_files}</b>`);
  }
  if (v.latest_eval_tag) {
    parts.push(`latest_eval_tag: <b>${esc(v.latest_eval_tag)}</b>`);
  }
  node.innerHTML = parts.join(" | ");
}

function renderTable(tableId, rows) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  if (!tbody) return;
  tbody.innerHTML = "";
  for (const r of rows || []) {
    const tr = document.createElement("tr");
    if (r.rank === 1) tr.className = "top1";
    tr.innerHTML = `
      <td>${r.rank}</td>
      <td>${esc(r.id)}</td>
      <td>${Number(r.elo).toFixed(2)}</td>
      <td>${r.games}</td>
      <td>${pct(r.win_rate)}</td>
      <td>${pct(r.score_rate)}</td>
    `;
    tbody.appendChild(tr);
  }
}

function shortCode(s) {
  const v = String(s || "");
  return v.length > 12 ? `${v.slice(0, 8)}...${v.slice(-4)}` : v;
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

async function reload() {
  try {
    const res = await fetch(`/api/elo?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    document.getElementById("host").textContent = `host: ${data.hostname || "-"}`;
    document.getElementById("generatedAt").textContent = `更新时间: ${data.generated_at || "-"}`;
    renderSummary("summary-prod", data.views?.prod);
    renderSummary("summary-iter", data.views?.iter);
    renderSaibloSummary("summary-saiblo-game1", data.views?.saiblo_game1);
    renderTable("table-prod", data.views?.prod?.rows || []);
    renderTable("table-iter", data.views?.iter?.rows || []);
    renderSaibloTable("table-saiblo-game1", data.views?.saiblo_game1?.rows || []);
  } catch (e) {
    document.getElementById("generatedAt").innerHTML = `<span class="err">加载失败: ${esc(e.message)}</span>`;
  }
}

reload();
setInterval(reload, 15000);
