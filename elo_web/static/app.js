function pct(v) {
  return `${(v * 100).toFixed(1)}%`;
}

function esc(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
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

async function reload() {
  try {
    const res = await fetch(`/api/elo?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    document.getElementById("host").textContent = `host: ${data.hostname || "-"}`;
    document.getElementById("generatedAt").textContent = `更新时间: ${data.generated_at || "-"}`;
    renderSummary("summary-prod", data.views?.prod);
    renderSummary("summary-iter", data.views?.iter);
    renderTable("table-prod", data.views?.prod?.rows || []);
    renderTable("table-iter", data.views?.iter?.rows || []);
  } catch (e) {
    document.getElementById("generatedAt").innerHTML = `<span class="err">加载失败: ${esc(e.message)}</span>`;
  }
}

reload();
setInterval(reload, 15000);
