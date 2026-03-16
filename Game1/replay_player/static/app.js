const state = {
  map: null,
  meta: null,
  replayPath: '',
  frames: [],
  frameSummaries: [],
  current: 0,
  playing: false,
  speed: 1,
  timer: null,
  geometry: null,
  selectedKey: null,
  selectedInfo: '点击棋盘查看格子、蚂蚁和塔信息。',
};

const OP_LABELS = {
  11: '建塔',
  12: '升级',
  13: '降级/拆塔',
  21: '闪电风暴',
  22: 'EMP',
  23: '偏导护盾',
  24: '紧急避险',
  31: '升级产速',
  32: '升级蚂蚁等级',
};

const TERRAIN_COLORS = {
  path: '#a8d4fb',
  barrier: '#f4efe4',
  p0_highland: '#e89097',
  p1_highland: '#a8f0c7',
  base0: '#de4137',
  base1: '#2346f7',
};

const BEHAVIOR_COLORS = {
  0: '#2f2b26',
  1: '#f59e0b',
  2: '#6b7280',
  3: '#7c3aed',
  4: '#10b981',
};

const dom = {};

function $(id) {
  return document.getElementById(id);
}

function initDom() {
  [
    'pathInput', 'loadPathBtn', 'fileInput', 'rootInput', 'scanBtn',
    'playBtn', 'pauseBtn', 'prevBtn', 'nextBtn', 'speedSelect',
    'jumpInput', 'jumpBtn', 'timeline', 'boardCanvas', 'roundLabel',
    'overviewRound', 'overviewTotal', 'winnerLabel', 'opsCountLabel',
    'replayPathLabel', 'seedLabel', 'player0Stats', 'player1Stats',
    'weaponPanel', 'op0List', 'op1List', 'selectionPanel', 'fileList'
  ].forEach((id) => { dom[id] = $(id); });
  dom.canvasWrap = $('canvasWrap');
  dom.boardCard = document.querySelector('.board-card');
  dom.controlsRow = document.querySelector('.controls');
  dom.sliderRow = document.querySelector('.slider-row');
  dom.ctx = dom.boardCanvas.getContext('2d');
}

async function fetchJson(url) {
  const res = await fetch(url);
  const obj = await res.json();
  if (!res.ok) throw new Error(obj.error || `HTTP ${res.status}`);
  return obj;
}

async function boot() {
  initDom();
  bindEvents();
  const [map, meta] = await Promise.all([
    fetchJson('/api/map'),
    fetchJson('/api/meta'),
  ]);
  state.map = map;
  state.meta = meta;
  state.geometry = buildGeometry(map, dom.boardCanvas.width, dom.boardCanvas.height);
  syncBoardViewport();
  renderBoard();
  await scanReplayRoots();

  const params = new URLSearchParams(window.location.search);
  const path = params.get('path');
  if (path) {
    dom.pathInput.value = path;
    await loadReplayFromPath(path);
  }
}

function bindEvents() {
  dom.loadPathBtn.addEventListener('click', () => loadReplayFromPath(dom.pathInput.value.trim()));
  dom.scanBtn.addEventListener('click', () => scanReplayRoots(dom.rootInput.value.trim()));
  dom.fileInput.addEventListener('change', handleLocalFile);
  dom.playBtn.addEventListener('click', play);
  dom.pauseBtn.addEventListener('click', pause);
  dom.prevBtn.addEventListener('click', () => stepTo(state.current - 1));
  dom.nextBtn.addEventListener('click', () => stepTo(state.current + 1));
  dom.jumpBtn.addEventListener('click', () => stepTo(Number(dom.jumpInput.value || 0)));
  dom.timeline.addEventListener('input', (e) => stepTo(Number(e.target.value || 0), false));
  dom.speedSelect.addEventListener('change', () => {
    state.speed = Number(dom.speedSelect.value || 1);
    if (state.playing) {
      pause();
      play();
    }
  });
  dom.boardCanvas.addEventListener('click', handleBoardClick);
  window.addEventListener('resize', () => syncBoardViewport());
  window.addEventListener('keydown', (e) => {
    if (e.target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
    if (e.code === 'Space') {
      e.preventDefault();
      state.playing ? pause() : play();
    } else if (e.code === 'ArrowLeft') {
      e.preventDefault();
      stepTo(state.current - 1);
    } else if (e.code === 'ArrowRight') {
      e.preventDefault();
      stepTo(state.current + 1);
    }
  });
}

function play() {
  if (!state.frames.length) return;
  pause();
  state.playing = true;
  const interval = Math.max(30, Math.round(1000 / state.speed));
  state.timer = window.setInterval(() => {
    if (state.current >= state.frames.length - 1) {
      pause();
      return;
    }
    stepTo(state.current + 1, false);
  }, interval);
}

function pause() {
  state.playing = false;
  if (state.timer) {
    window.clearInterval(state.timer);
    state.timer = null;
  }
}

function syncBoardViewport() {
  if (!dom.canvasWrap || !dom.boardCard) return;
  const controlsH = dom.controlsRow?.offsetHeight || 0;
  const sliderH = dom.sliderRow?.offsetHeight || 0;
  const reserved = controlsH + sliderH + 28;
  const maxByWidth = Math.max(320, dom.boardCard.clientWidth - 20);
  const maxByHeight = Math.max(320, dom.boardCard.clientHeight - reserved);
  const side = Math.max(320, Math.min(maxByWidth, maxByHeight));
  dom.canvasWrap.style.width = `${side}px`;
  dom.canvasWrap.style.height = `${side}px`;
}

function buildGeometry(map, width, height) {
  const size = 24;
  const sqrt3 = Math.sqrt(3);
  const rawCenters = map.cells.map((cell) => {
    const q = cell.y;
    const r = cell.x - (cell.y - (cell.y & 1)) / 2;
    const px = size * sqrt3 * (q + r / 2);
    const py = size * 1.5 * r;
    return { ...cell, px, py };
  });
  const minX = Math.min(...rawCenters.map((x) => x.px));
  const maxX = Math.max(...rawCenters.map((x) => x.px));
  const minY = Math.min(...rawCenters.map((x) => x.py));
  const maxY = Math.max(...rawCenters.map((x) => x.py));
  const padding = 56;
  const boardW = maxX - minX;
  const boardH = maxY - minY;
  const scale = Math.min((width - padding * 2) / (boardW + size * 2), (height - padding * 2) / (boardH + size * 2));
  const finalSize = size * scale;
  const xOffset = (width - (boardW + finalSize * 2)) / 2 - minX * scale + finalSize;
  const yOffset = (height - (boardH + finalSize * 2)) / 2 - minY * scale + finalSize;
  const cells = rawCenters.map((cell) => ({
    ...cell,
    px: cell.px * scale + xOffset,
    py: cell.py * scale + yOffset,
  }));
  const cellMap = new Map(cells.map((cell) => [`${cell.x},${cell.y}`, cell]));
  return { size: finalSize, cells, cellMap };
}

function hexPoints(cx, cy, size) {
  const pts = [];
  for (let i = 0; i < 6; i += 1) {
    const angle = (Math.PI / 180) * (60 * i - 30);
    pts.push({ x: cx + size * Math.cos(angle), y: cy + size * Math.sin(angle) });
  }
  return pts;
}

function normalizeReplayFrames(payload) {
  if (!Array.isArray(payload)) throw new Error('回放根节点不是 JSON 数组');
  return payload.map((frame, index) => ({
    index,
    op0: Array.isArray(frame.op0) ? frame.op0 : [],
    op1: Array.isArray(frame.op1) ? frame.op1 : [],
    round_state: frame.round_state || {},
    seed: frame.seed ?? null,
  }));
}

function computeFrameSummaries(frames) {
  const weaponDefs = state.meta.weaponTypes;
  const cooldowns = [new Map(), new Map()];
  const activeEffects = [[], []];
  const out = [];
  const pushUsedOp = (list, player, op) => {
    const type = Number(op.type);
    if (type < 21 || type > 24) return;
    const weaponType = type % 10;
    const def = weaponDefs[String(weaponType)];
    if (!def) return;
    cooldowns[player].set(weaponType, def.cooldown);
    activeEffects[player].push({
      type: weaponType,
      label: def.name,
      x: op.pos?.x ?? -1,
      y: op.pos?.y ?? -1,
      remaining: def.duration,
      drifting: weaponType === 1 || weaponType === 2,
    });
  };

  frames.forEach((frame) => {
    frame.op0.forEach((op) => pushUsedOp(out, 0, op));
    frame.op1.forEach((op) => pushUsedOp(out, 1, op));

    for (const player of [0, 1]) {
      for (const [weaponType, cd] of Array.from(cooldowns[player].entries())) {
        cooldowns[player].set(weaponType, Math.max(0, cd - 1));
      }
      activeEffects[player] = activeEffects[player]
        .map((effect) => ({ ...effect, remaining: effect.remaining - 1 }))
        .filter((effect) => effect.remaining > 0 && effect.type !== 4);
    }

    out.push({
      seed: frame.seed,
      weaponCooldowns: [0, 1].map((player) => {
        const values = {};
        for (const key of ['1', '2', '3', '4']) values[key] = cooldowns[player].get(Number(key)) || 0;
        return values;
      }),
      activeEffects: [0, 1].map((player) => activeEffects[player].map((item) => ({ ...item }))),
    });
  });
  return out;
}

function summarizeOps(frameIndex, frame) {
  const prev = frameIndex > 0 ? state.frames[frameIndex - 1].round_state : null;
  const curr = frame.round_state;
  const resolvePos = (op) => {
    if (op.pos && op.pos.x >= 0 && op.pos.y >= 0) return op.pos;
    const towerId = Number(op.id ?? -1);
    const lookup = (stateObj) => {
      const towers = Array.isArray(stateObj?.towers) ? stateObj.towers : [];
      const tower = towers.find((item) => Number(item.id) === towerId);
      return tower?.pos || null;
    };
    return lookup(prev) || lookup(curr) || null;
  };
  const formatSide = (ops) => ops.map((op) => {
    const type = Number(op.type);
    const pos = resolvePos(op);
    const label = OP_LABELS[type] || `OP ${type}`;
    if (type === 12 && Number(op.args) >= 0) {
      const towerName = state.meta.towerTypes[String(op.args)]?.name || String(op.args);
      return { label: `${label} -> ${towerName}`, pos, type };
    }
    if (type === 13) {
      return { label: `${label} #${op.id}`, pos, type };
    }
    if (type >= 21 && type <= 24) {
      return { label: `${label} @ (${pos?.x ?? '?'}, ${pos?.y ?? '?'})`, pos, type };
    }
    if (type === 31 || type === 32) {
      return { label, pos: null, type };
    }
    return { label: `${label} @ (${pos?.x ?? '?'}, ${pos?.y ?? '?'})`, pos, type };
  });
  return { op0: formatSide(frame.op0), op1: formatSide(frame.op1) };
}

async function scanReplayRoots(root = '') {
  try {
    const url = root ? `/api/list?root=${encodeURIComponent(root)}` : '/api/list';
    const data = await fetchJson(url);
    renderFileList(data.roots || []);
  } catch (err) {
    dom.fileList.innerHTML = `<div class="file-item">扫描失败: ${escapeHtml(String(err.message || err))}</div>`;
  }
}

function renderFileList(groups) {
  if (!groups.length) {
    dom.fileList.innerHTML = '<div class="file-item">未找到 replay 文件。</div>';
    return;
  }
  dom.fileList.innerHTML = '';
  groups.forEach((group) => {
    const title = document.createElement('div');
    title.className = 'file-item';
    title.innerHTML = `<div class="name">${escapeHtml(group.root)}</div><div class="meta">${group.files.length} files</div>`;
    dom.fileList.appendChild(title);
    group.files.forEach((file) => {
      const item = document.createElement('div');
      item.className = 'file-item';
      item.innerHTML = `<div class="name">${escapeHtml(file.name)}</div><div class="meta">${escapeHtml(file.path)} | ${(file.size / 1024).toFixed(1)} KB</div>`;
      item.addEventListener('click', () => {
        dom.pathInput.value = file.path;
        loadReplayFromPath(file.path);
      });
      dom.fileList.appendChild(item);
    });
  });
}

async function loadReplayFromPath(path) {
  if (!path) return;
  pause();
  const data = await fetchJson(`/api/replay?path=${encodeURIComponent(path)}`);
  loadReplayData(data.frames, data.path);
}

function handleLocalFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  pause();
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const parsed = JSON.parse(String(reader.result));
      loadReplayData(parsed, file.name, true);
    } catch (err) {
      alert(`本地文件解析失败: ${err.message || err}`);
    }
  };
  reader.readAsText(file, 'utf-8');
}

function loadReplayData(rawFrames, label, local = false) {
  state.frames = normalizeReplayFrames(rawFrames);
  state.frameSummaries = computeFrameSummaries(state.frames);
  state.replayPath = label;
  state.current = 0;
  state.selectedKey = null;
  state.selectedInfo = '点击棋盘查看格子、蚂蚁和塔信息。';
  dom.timeline.min = '0';
  dom.timeline.max = String(Math.max(0, state.frames.length - 1));
  dom.timeline.value = '0';
  dom.jumpInput.value = '0';
  dom.replayPathLabel.textContent = local ? `本地文件: ${label}` : label;
  dom.seedLabel.textContent = `Seed: ${state.frames[0]?.seed ?? '-'}`;
  const url = new URL(window.location.href);
  if (!local) url.searchParams.set('path', label);
  else url.searchParams.delete('path');
  window.history.replaceState({}, '', url);
  syncBoardViewport();
  renderCurrentFrame();
}

function stepTo(index, clamp = true) {
  if (!state.frames.length) return;
  let next = index;
  if (clamp) next = Math.max(0, Math.min(state.frames.length - 1, next));
  if (next < 0 || next >= state.frames.length) return;
  state.current = next;
  dom.timeline.value = String(next);
  dom.jumpInput.value = String(next);
  renderCurrentFrame();
}

function currentFrame() {
  return state.frames[state.current] || null;
}

function renderCurrentFrame() {
  renderBoard();
  renderInfoPanels();
}

function renderBoard() {
  const ctx = dom.ctx;
  const { width, height } = dom.boardCanvas;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = '#fff9ef';
  ctx.fillRect(0, 0, width, height);

  if (!state.geometry) return;
  const frame = currentFrame();
  const roundState = frame?.round_state || {};
  const towers = Array.isArray(roundState.towers) ? roundState.towers : [];
  const ants = Array.isArray(roundState.ants) ? roundState.ants : [];
  const ops = frame ? summarizeOps(state.current, frame) : { op0: [], op1: [] };
  const opHighlights = [...ops.op0, ...ops.op1].filter((item) => item.pos);

  state.geometry.cells.forEach((cell) => {
    const points = hexPoints(cell.px, cell.py, state.geometry.size - 1);
    ctx.beginPath();
    points.forEach((pt, idx) => {
      if (idx === 0) ctx.moveTo(pt.x, pt.y);
      else ctx.lineTo(pt.x, pt.y);
    });
    ctx.closePath();
    ctx.fillStyle = TERRAIN_COLORS[cell.terrain] || '#b7b7b7';
    ctx.fill();
    ctx.strokeStyle = '#7b7366';
    ctx.lineWidth = 1.4;
    ctx.stroke();
  });

  opHighlights.forEach((item) => {
    const cell = state.geometry.cellMap.get(`${item.pos.x},${item.pos.y}`);
    if (!cell) return;
    ctx.beginPath();
    ctx.arc(cell.px, cell.py, state.geometry.size * 0.78, 0, Math.PI * 2);
    ctx.strokeStyle = item.type >= 21 ? '#111827' : '#f59e0b';
    ctx.lineWidth = 4;
    ctx.stroke();
  });

  towers.forEach((tower) => {
    const x = Number(tower.pos?.x);
    const y = Number(tower.pos?.y);
    const cell = state.geometry.cellMap.get(`${x},${y}`);
    if (!cell) return;
    const player = Number(tower.player || 0);
    const towerMeta = state.meta.towerTypes[String(Number(tower.type))] || { label: String(tower.type), name: `T${tower.type}` };
    ctx.beginPath();
    ctx.arc(cell.px, cell.py, state.geometry.size * 0.46, 0, Math.PI * 2);
    ctx.fillStyle = player === 0 ? '#a8211a' : '#1233b8';
    ctx.fill();
    ctx.strokeStyle = '#fff8ef';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = '#fffaf1';
    ctx.font = `bold ${Math.max(10, state.geometry.size * 0.36)}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(towerMeta.label, cell.px, cell.py + 1);
    if (Number(tower.cd || 0) > 0) {
      ctx.fillStyle = '#1f2937';
      ctx.font = `bold ${Math.max(8, state.geometry.size * 0.24)}px sans-serif`;
      ctx.fillText(String(Math.round(Number(tower.cd))), cell.px + state.geometry.size * 0.42, cell.py - state.geometry.size * 0.46);
    }
  });

  const antsByCell = new Map();
  ants.forEach((ant) => {
    const key = `${ant.pos?.x},${ant.pos?.y}`;
    if (!antsByCell.has(key)) antsByCell.set(key, []);
    antsByCell.get(key).push(ant);
  });

  antsByCell.forEach((cellAnts, key) => {
    const cell = state.geometry.cellMap.get(key);
    if (!cell) return;
    const count = cellAnts.length;
    const spread = Math.min(state.geometry.size * 0.45, 10 + count * 1.5);
    cellAnts.forEach((ant, idx) => {
      const angle = count === 1 ? 0 : (Math.PI * 2 * idx) / count;
      const ox = count === 1 ? 0 : Math.cos(angle) * spread * 0.5;
      const oy = count === 1 ? 0 : Math.sin(angle) * spread * 0.5;
      const radius = Math.max(8, state.geometry.size * 0.26);
      ctx.beginPath();
      ctx.arc(cell.px + ox, cell.py + oy, radius, 0, Math.PI * 2);
      ctx.fillStyle = Number(ant.player) === 0 ? '#ff5b4d' : '#3760ff';
      ctx.fill();
      ctx.strokeStyle = BEHAVIOR_COLORS[String(ant.behavior)] || '#111827';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = '#ffffff';
      ctx.font = `bold ${Math.max(9, state.geometry.size * 0.26)}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(Number(ant.level) + 1), cell.px + ox, cell.py + oy + 0.5);
    });
  });

  state.map.bases.forEach((base) => {
    const cell = state.geometry.cellMap.get(`${base.x},${base.y}`);
    if (!cell) return;
    ctx.beginPath();
    ctx.arc(cell.px, cell.py, state.geometry.size * 0.58, 0, Math.PI * 2);
    ctx.fillStyle = base.player === 0 ? '#de4137' : '#2346f7';
    ctx.fill();
    ctx.strokeStyle = '#fffef8';
    ctx.lineWidth = 3;
    ctx.stroke();
  });

  if (state.selectedKey) {
    const cell = state.geometry.cellMap.get(state.selectedKey);
    if (cell) {
      ctx.beginPath();
      ctx.arc(cell.px, cell.py, state.geometry.size * 0.92, 0, Math.PI * 2);
      ctx.strokeStyle = '#111827';
      ctx.lineWidth = 3;
      ctx.stroke();
    }
  }
}

function renderInfoPanels() {
  const frame = currentFrame();
  if (!frame) return;
  const roundState = frame.round_state || {};
  const ops = summarizeOps(state.current, frame);
  const summary = state.frameSummaries[state.current] || null;
  const towers = Array.isArray(roundState.towers) ? roundState.towers : [];
  const ants = Array.isArray(roundState.ants) ? roundState.ants : [];
  const p0Towers = towers.filter((x) => Number(x.player) === 0).length;
  const p1Towers = towers.filter((x) => Number(x.player) === 1).length;
  const p0Ants = ants.filter((x) => Number(x.player) === 0).length;
  const p1Ants = ants.filter((x) => Number(x.player) === 1).length;
  const winner = Number(roundState.winner ?? -1);

  dom.roundLabel.textContent = `Round ${state.current} / ${Math.max(0, state.frames.length - 1)}`;
  dom.overviewRound.textContent = String(state.current);
  dom.overviewTotal.textContent = String(state.frames.length);
  dom.winnerLabel.textContent = winner >= 0 ? `Player ${winner}` : '进行中';
  dom.opsCountLabel.textContent = String(ops.op0.length + ops.op1.length);

  renderPlayerStats(0, {
    hp: roundState.camps?.[0] ?? '-',
    coins: roundState.coins?.[0] ?? '-',
    antLv: roundState.anthpLv?.[0] ?? '-',
    genLv: roundState.speedLv?.[0] ?? '-',
    towers: p0Towers,
    ants: p0Ants,
  });
  renderPlayerStats(1, {
    hp: roundState.camps?.[1] ?? '-',
    coins: roundState.coins?.[1] ?? '-',
    antLv: roundState.anthpLv?.[1] ?? '-',
    genLv: roundState.speedLv?.[1] ?? '-',
    towers: p1Towers,
    ants: p1Ants,
  });

  renderOpsList(dom.op0List, ops.op0);
  renderOpsList(dom.op1List, ops.op1);
  renderWeapons(summary);
  dom.selectionPanel.textContent = state.selectedInfo;
}

function renderPlayerStats(player, stats) {
  const target = player === 0 ? dom.player0Stats : dom.player1Stats;
  target.innerHTML = '';
  const order = [
    ['基地 HP', stats.hp],
    ['金币', stats.coins],
    ['蚂蚁等级', stats.antLv],
    ['产速等级', stats.genLv],
    ['塔数', stats.towers],
    ['蚂蚁数', stats.ants],
  ];
  order.forEach(([k, v]) => {
    const el = document.createElement('div');
    el.className = 'kv';
    el.innerHTML = `<span>${k}</span><strong>${escapeHtml(String(v))}</strong>`;
    target.appendChild(el);
  });
}

function renderOpsList(target, items) {
  target.innerHTML = '';
  if (!items.length) {
    const li = document.createElement('li');
    li.textContent = '无';
    target.appendChild(li);
    return;
  }
  items.forEach((item) => {
    const li = document.createElement('li');
    li.textContent = item.label;
    target.appendChild(li);
  });
}

function renderWeapons(summary) {
  dom.weaponPanel.innerHTML = '';
  if (!summary) return;
  [0, 1].forEach((player) => {
    const block = document.createElement('div');
    block.className = 'weapon-player';
    const title = document.createElement('h3');
    title.textContent = `Player ${player}`;
    title.style.margin = '0';
    title.style.color = player === 0 ? 'var(--p0)' : 'var(--p1)';
    block.appendChild(title);
    const grid = document.createElement('div');
    grid.className = 'weapon-grid';
    Object.entries(state.meta.weaponTypes).forEach(([weaponId, def]) => {
      const cd = summary.weaponCooldowns[player]?.[weaponId] ?? 0;
      const active = (summary.activeEffects[player] || []).filter((x) => String(x.type) === weaponId);
      const item = document.createElement('div');
      item.className = 'weapon-item';
      const activeText = active.length
        ? active.map((x) => `剩余 ${x.remaining}${x.drifting ? ' | 位置为估计起点' : ''}`).join(' / ')
        : '未激活';
      item.innerHTML = `<strong>${def.name}</strong><div>CD: ${cd}</div><div>${activeText}</div>`;
      grid.appendChild(item);
    });
    block.appendChild(grid);
    dom.weaponPanel.appendChild(block);
  });
}

function handleBoardClick(event) {
  if (!state.geometry || !state.frames.length) return;
  const rect = dom.boardCanvas.getBoundingClientRect();
  const scaleX = dom.boardCanvas.width / rect.width;
  const scaleY = dom.boardCanvas.height / rect.height;
  const px = (event.clientX - rect.left) * scaleX;
  const py = (event.clientY - rect.top) * scaleY;
  let best = null;
  let bestDist = Infinity;
  state.geometry.cells.forEach((cell) => {
    const dist = Math.hypot(cell.px - px, cell.py - py);
    if (dist < bestDist) {
      bestDist = dist;
      best = cell;
    }
  });
  if (!best || bestDist > state.geometry.size) return;
  state.selectedKey = `${best.x},${best.y}`;
  state.selectedInfo = buildSelectionInfo(best.x, best.y);
  renderCurrentFrame();
}

function buildSelectionInfo(x, y) {
  const frame = currentFrame();
  const roundState = frame?.round_state || {};
  const towers = (roundState.towers || []).filter((t) => Number(t.pos?.x) === x && Number(t.pos?.y) === y);
  const ants = (roundState.ants || []).filter((a) => Number(a.pos?.x) === x && Number(a.pos?.y) === y);
  const terrain = state.geometry.cellMap.get(`${x},${y}`)?.terrain || 'unknown';
  const lines = [`坐标: (${x}, ${y})`, `地形: ${terrain}`];
  const base = state.map.bases.find((b) => b.x === x && b.y === y);
  if (base) {
    lines.push(`基地: Player ${base.player}`);
    lines.push(`基地 HP: ${roundState.camps?.[base.player] ?? '-'}`);
    lines.push(`蚂蚁等级: ${roundState.anthpLv?.[base.player] ?? '-'}`);
    lines.push(`产速等级: ${roundState.speedLv?.[base.player] ?? '-'}`);
  }
  if (towers.length) {
    lines.push('塔:');
    towers.forEach((tower) => {
      const meta = state.meta.towerTypes[String(Number(tower.type))];
      lines.push(`- #${tower.id} P${tower.player} ${meta?.name || tower.type} cd=${tower.cd}`);
    });
  }
  if (ants.length) {
    lines.push('蚂蚁:');
    ants.forEach((ant) => {
      lines.push(`- #${ant.id} P${ant.player} lv=${Number(ant.level) + 1} hp=${ant.hp} age=${ant.age} status=${state.meta.statuses[String(ant.status)]} behavior=${state.meta.behaviors[String(ant.behavior)]}`);
    });
  }
  if (!towers.length && !ants.length && !base) lines.push('当前无单位。');
  return lines.join('\n');
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

boot().catch((err) => {
  alert(`播放器初始化失败: ${err.message || err}`);
});
