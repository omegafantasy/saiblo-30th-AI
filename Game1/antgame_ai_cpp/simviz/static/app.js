const appState = {
  map: null,
  replayMeta: null,
  replayRound: null,
  actions: null,
  selectedPlanKey: null,
  rollouts: null,
  selectedSampleIndex: null,
  trace: null,
  selectedTraceStep: 0,
  boardMode: "replay",
  slotByPlayerCoord: new Map(),
  boardViews: {},
};

const STRATEGY_ROLLOUT_COUNT = 50;

const dom = {};
const layoutState = {
  activeDivider: null,
  startX: 0,
  startLeftWidth: 0,
  startMiddleWidth: 0,
  startRightWidth: 0,
};
const roundLoadState = {
  debounceTimer: null,
  requestSerial: 0,
};

const WORKSPACE_MIN_LEFT = 320;
const WORKSPACE_MIN_MIDDLE = 360;
const WORKSPACE_MIN_RIGHT = 380;

function $(id) {
  return document.getElementById(id);
}

function setStatus(text, isError = false) {
  const node = dom.statusText;
  node.textContent = text;
  node.style.background = isError ? "#f3d0ca" : "";
  node.style.borderColor = isError ? "#a84740" : "";
}

function syncRoundControls(round) {
  const clamped = clampRound(round);
  dom.roundInput.value = String(clamped);
  dom.roundSlider.value = String(clamped);
  return clamped;
}

function cancelScheduledRoundLoad() {
  if (roundLoadState.debounceTimer != null) {
    window.clearTimeout(roundLoadState.debounceTimer);
    roundLoadState.debounceTimer = null;
  }
}

function scheduleRoundLoad(delayMs = 140) {
  if (!appState.replayMeta) return;
  const round = syncRoundControls(Number(dom.roundSlider.value || dom.roundInput.value || 0));
  cancelScheduledRoundLoad();
  roundLoadState.debounceTimer = window.setTimeout(() => {
    roundLoadState.debounceTimer = null;
    loadRound(round);
  }, delayMs);
}

async function postJSON(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  if (!resp.ok || data.ok === false) {
    throw new Error(data.error || `request failed: ${resp.status}`);
  }
  return data;
}

async function getJSON(url) {
  const resp = await fetch(url);
  const data = await resp.json();
  if (!resp.ok || data.ok === false) {
    throw new Error(data.error || `request failed: ${resp.status}`);
  }
  return data;
}

function buildSlotLookups() {
  appState.slotByPlayerCoord.clear();
  for (const slot of appState.map.slots) {
    appState.slotByPlayerCoord.set(`${slot.player}:${slot.x}:${slot.y}`, slot.name);
  }
}

function slotName(player, x, y) {
  return appState.slotByPlayerCoord.get(`${player}:${x}:${y}`) || `(${x},${y})`;
}

function clampRound(value) {
  if (!appState.replayMeta) return 0;
  return Math.max(0, Math.min(appState.replayMeta.round_count - 1, value));
}

function terrainColor(terrain) {
  switch (terrain) {
    case 0:
      return "#f7f1df";
    case 1:
      return "#2f3b45";
    case 2:
      return "#d9ecff";
    case 3:
      return "#ffe0e0";
    default:
      return "#ffffff";
  }
}

function playerColor(player) {
  return player === 0 ? "#2f5d8a" : "#a84740";
}

function effectColor(name) {
  if (name.includes("Lightning")) return "#b68b2d";
  if (name.includes("Emp")) return "#404b8a";
  if (name.includes("Deflector")) return "#3d8a5a";
  if (name.includes("Emergency")) return "#8a4f8c";
  return "#666666";
}

function effectRange(name) {
  if (name.includes("Lightning")) return 3;
  if (name.includes("Emp")) return 3;
  if (name.includes("Deflector")) return 3;
  if (name.includes("Emergency")) return 3;
  return 0;
}

function towerTypeName(type) {
  const map = {
    0: "Basic",
    1: "Heavy",
    2: "Quick",
    3: "Mortar",
    4: "Producer",
    11: "HeavyPlus",
    12: "Ice",
    13: "Bewitch",
    21: "QuickPlus",
    22: "Double",
    23: "Sniper",
    31: "MortarPlus",
    32: "Pulse",
    33: "Missile",
    41: "ProducerFast",
    42: "ProducerSiege",
    43: "ProducerMedic",
  };
  return map[type] || `T${type}`;
}

function hexDistance(x0, y0, x1, y1) {
  const dy = Math.abs(y0 - y1);
  let dx = 0;
  if (dy % 2) {
    if (x0 > x1) {
      dx = Math.max(0, Math.abs(x0 - x1) - Math.floor(dy / 2) - (y0 % 2));
    } else {
      dx = Math.max(0, Math.abs(x0 - x1) - Math.floor(dy / 2) - (1 - (y0 % 2)));
    }
  } else {
    dx = Math.max(0, Math.abs(x0 - x1) - Math.floor(dy / 2));
  }
  return dx + dy;
}

function highlightColor(kind) {
  switch (kind) {
    case "build":
      return "#198754";
    case "upgrade":
      return "#0d6efd";
    case "downgrade":
      return "#c0392b";
    case "lightning":
      return "#b68b2d";
    default:
      return "#9f4f2c";
  }
}

function centerXY(x, y, radius) {
  const stepX = 1.5 * radius;
  const baseX = stepX * x - 0.5 * stepX * (y & 1);
  const baseY = Math.sqrt(3) * 0.5 * stepX * y;
  return {
    x: baseY,
    y: -baseX,
  };
}

function hexPoints(cx, cy, radius) {
  const pts = [];
  for (let i = 0; i < 6; i += 1) {
    const angle = (Math.PI / 180) * (60 * i);
    pts.push(`${cx + radius * Math.cos(angle)},${cy + radius * Math.sin(angle)}`);
  }
  return pts.join(" ");
}

function createSvg(tag) {
  return document.createElementNS("http://www.w3.org/2000/svg", tag);
}

function addTitle(node, text) {
  const title = createSvg("title");
  title.textContent = text;
  node.appendChild(title);
}

function normalizePublicState(raw) {
  const towersRaw = raw.towers || [];
  const antsRaw = raw.ants || [];
  const effectsRaw = raw.active_effects || raw.activeEffects || [];
  const coins = raw.coins || [0, 0];
  const camps = raw.camps_hp || raw.camps || [null, null];
  return {
    kind: "public",
    towers: towersRaw.map((tower) => ({
      id: tower.id ?? tower.tower_id ?? -1,
      player: tower.player ?? -1,
      x: tower.x ?? tower.pos?.x ?? -1,
      y: tower.y ?? tower.pos?.y ?? -1,
      type: tower.type ?? tower.tower_type ?? -1,
      typeName: tower.type_name || tower.typeName || towerTypeName(tower.type ?? tower.tower_type ?? -1),
      hp: tower.hp ?? 0,
      maxHp: tower.max_hp ?? tower.maxHp ?? tower.hp ?? 0,
      cooldown: tower.cooldown ?? tower.cd ?? 0,
    })),
    ants: antsRaw.map((ant) => ({
      id: ant.id ?? ant.ant_id ?? -1,
      player: ant.player ?? -1,
      x: ant.x ?? ant.pos?.x ?? -1,
      y: ant.y ?? ant.pos?.y ?? -1,
      hp: ant.hp ?? 0,
      maxHp: ant.max_hp ?? ant.maxHp ?? ant.hp ?? 0,
      kind: ant.kind ?? 0,
      kindName: ant.kind_name || ant.kindName || (ant.kind === 1 ? "Combat" : "Worker"),
      behavior: ant.behavior ?? 0,
      behaviorName:
        ant.behavior_name ||
        ant.behaviorName ||
        ["Default", "Conservative", "Random", "Bewitched", "ControlFree"][ant.behavior ?? 0] ||
        "Unknown",
      shield: ant.shield ?? 0,
    })),
    effects: effectsRaw.map((effect) => ({
      player: effect.player ?? -1,
      x: effect.x ?? -1,
      y: effect.y ?? -1,
      weaponName: effect.weapon_name || effect.weaponName || "Effect",
      remainingTurns: effect.remaining_turns ?? effect.remainingTurns ?? 0,
    })),
    baseHp: { 0: camps[0], 1: camps[1] },
    coins: { 0: coins[0], 1: coins[1] },
  };
}

function normalizeDefenseState(raw) {
  return {
    kind: "defense",
    player: raw.player,
    enemy: raw.enemy,
    towers: (raw.towers || []).map((tower) => ({
      id: tower.id,
      player: raw.player,
      x: tower.x,
      y: tower.y,
      type: tower.type,
      typeName: tower.type_name || `T${tower.type}`,
      hp: tower.hp,
      maxHp: tower.max_hp || tower.hp,
      cooldown: tower.cooldown || 0,
    })),
    ants: (raw.ants || []).map((ant) => ({
      id: ant.id,
      player: raw.enemy,
      x: ant.x,
      y: ant.y,
      hp: ant.hp,
      maxHp: ant.max_hp || ant.hp,
      kind: ant.kind,
      kindName: ant.kind_name || (ant.kind === 1 ? "Combat" : "Worker"),
      behavior: ant.behavior,
      behaviorName: ant.behavior_name || "Unknown",
      shield: ant.shield || 0,
    })),
    effects: [
      ...(raw.my_effects || []).map((effect) => ({
        player: raw.player,
        x: effect.x,
        y: effect.y,
        weaponName: effect.weapon_name || "Effect",
        remainingTurns: effect.remaining_turns || 0,
      })),
      ...(raw.enemy_effects || []).map((effect) => ({
        player: raw.enemy,
        x: effect.x,
        y: effect.y,
        weaponName: effect.weapon_name || "Effect",
        remainingTurns: effect.remaining_turns || 0,
      })),
    ],
    baseHp: { [raw.player]: raw.base_hp },
    coins: { [raw.player]: raw.coins },
  };
}

function detectState(raw) {
  if (!raw) return null;
  if (raw.active_effects || raw.activeEffects || raw.camps || raw.camps_hp) {
    return normalizePublicState(raw);
  }
  if (Object.prototype.hasOwnProperty.call(raw, "base_hp")) {
    return normalizeDefenseState(raw);
  }
  return null;
}

function towerAbbrev(typeName) {
  const map = {
    Basic: "B",
    Heavy: "H",
    Quick: "Q",
    Mortar: "M",
    Producer: "P",
    HeavyPlus: "H+",
    Ice: "I",
    Bewitch: "BW",
    QuickPlus: "Q+",
    Double: "D",
    Sniper: "S",
    MortarPlus: "M+",
    Pulse: "PU",
    Missile: "MS",
  };
  return map[typeName] || typeName.slice(0, 2).toUpperCase();
}

function antAbbrev(kindName, behaviorName) {
  const kind = kindName.startsWith("Combat") ? "C" : "W";
  const behaviorMap = {
    Default: "",
    Conservative: "c",
    Random: "r",
    Bewitched: "b",
    ControlFree: "f",
  };
  return `${kind}${behaviorMap[behaviorName] || ""}`;
}

function formatNumber(value) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const num = Number(value);
  if (Math.abs(num) >= 1000 || (Math.abs(num) > 0 && Math.abs(num) < 0.001)) {
    return num.toExponential(2);
  }
  return num.toFixed(2).replace(/\.00$/, "");
}

function formatPlainNumber(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const num = Number(value);
  return num.toFixed(digits).replace(/\.00$/, "");
}

function sampleWeight(sample) {
  return sample?.normalized_path_weight ?? sample?.importance_weight ?? 0;
}

function workspaceDividerSize() {
  if (!dom.workspace) return 10;
  const value = getComputedStyle(dom.workspace).getPropertyValue("--divider-size").trim();
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 10;
}

function readWorkspaceWidths() {
  if (!dom.workspace || !dom.columnLeft || !dom.columnMiddle) {
    return { total: 0, left: 0, middle: 0, right: 0, dividerSize: 10 };
  }
  const total = dom.workspace.getBoundingClientRect().width;
  const dividerSize = workspaceDividerSize();
  const left = dom.columnLeft.getBoundingClientRect().width;
  const middle = dom.columnMiddle.getBoundingClientRect().width;
  const right = Math.max(0, total - left - middle - dividerSize * 2);
  return { total, left, middle, right, dividerSize };
}

function applyWorkspaceWidths(left, middle) {
  if (!dom.workspace) return;
  dom.workspace.style.setProperty("--left-col-width", `${Math.round(left)}px`);
  dom.workspace.style.setProperty("--middle-col-width", `${Math.round(middle)}px`);
}

function clampWorkspaceWidths(left, middle) {
  const metrics = readWorkspaceWidths();
  const usable = Math.max(0, metrics.total - metrics.dividerSize * 2);

  let nextLeft = Math.max(WORKSPACE_MIN_LEFT, left);
  let nextMiddle = Math.max(WORKSPACE_MIN_MIDDLE, middle);
  const maxLeft = Math.max(WORKSPACE_MIN_LEFT, usable - WORKSPACE_MIN_MIDDLE - WORKSPACE_MIN_RIGHT);
  nextLeft = Math.min(nextLeft, maxLeft);
  const maxMiddle = Math.max(WORKSPACE_MIN_MIDDLE, usable - nextLeft - WORKSPACE_MIN_RIGHT);
  nextMiddle = Math.min(nextMiddle, maxMiddle);

  const overflow = nextLeft + nextMiddle + WORKSPACE_MIN_RIGHT - usable;
  if (overflow > 0) {
    if (nextMiddle - WORKSPACE_MIN_MIDDLE >= overflow) {
      nextMiddle -= overflow;
    } else {
      const rest = overflow - (nextMiddle - WORKSPACE_MIN_MIDDLE);
      nextMiddle = WORKSPACE_MIN_MIDDLE;
      nextLeft = Math.max(WORKSPACE_MIN_LEFT, nextLeft - rest);
    }
  }
  return { left: nextLeft, middle: nextMiddle };
}

function resetWorkspaceWidths() {
  const metrics = readWorkspaceWidths();
  if (!metrics.total) return;
  const usable = Math.max(0, metrics.total - metrics.dividerSize * 2);
  const targetLeft = Math.round(Math.max(WORKSPACE_MIN_LEFT, Math.min(usable * 0.2, 390)));
  const targetMiddle = Math.round(Math.max(WORKSPACE_MIN_MIDDLE, Math.min(usable * 0.29, 520)));
  const clamped = clampWorkspaceWidths(targetLeft, targetMiddle);
  applyWorkspaceWidths(clamped.left, clamped.middle);
}

function syncWorkspaceWidths() {
  const metrics = readWorkspaceWidths();
  if (!metrics.total) return;
  const leftProp = dom.workspace.style.getPropertyValue("--left-col-width");
  const middleProp = dom.workspace.style.getPropertyValue("--middle-col-width");
  if (!leftProp || !middleProp) {
    resetWorkspaceWidths();
    return;
  }
  const clamped = clampWorkspaceWidths(metrics.left, metrics.middle);
  applyWorkspaceWidths(clamped.left, clamped.middle);
}

function stopDividerDrag() {
  if (!layoutState.activeDivider) return;
  layoutState.activeDivider.classList.remove("active");
  layoutState.activeDivider = null;
  document.body.classList.remove("resizing-columns");
  window.removeEventListener("pointermove", onDividerPointerMove);
  window.removeEventListener("pointerup", stopDividerDrag);
  window.removeEventListener("pointercancel", stopDividerDrag);
}

function onDividerPointerMove(event) {
  if (!layoutState.activeDivider) return;
  const delta = event.clientX - layoutState.startX;

  if (layoutState.activeDivider === dom.dividerLeft) {
    const nextLeft = layoutState.startLeftWidth + delta;
    const nextMiddle = layoutState.startMiddleWidth - delta;
    const clampedLeft = Math.max(
      WORKSPACE_MIN_LEFT,
      Math.min(nextLeft, layoutState.startLeftWidth + (layoutState.startMiddleWidth - WORKSPACE_MIN_MIDDLE))
    );
    const appliedDelta = clampedLeft - layoutState.startLeftWidth;
    applyWorkspaceWidths(clampedLeft, layoutState.startMiddleWidth - appliedDelta);
    return;
  }

  if (layoutState.activeDivider === dom.dividerRight) {
    const maxMiddle = layoutState.startMiddleWidth + Math.max(0, layoutState.startRightWidth - WORKSPACE_MIN_RIGHT);
    const nextMiddle = Math.max(WORKSPACE_MIN_MIDDLE, Math.min(layoutState.startMiddleWidth + delta, maxMiddle));
    applyWorkspaceWidths(layoutState.startLeftWidth, nextMiddle);
  }
}

function startDividerDrag(divider, event) {
  event.preventDefault();
  const metrics = readWorkspaceWidths();
  if (!metrics.total) return;
  layoutState.activeDivider = divider;
  layoutState.startX = event.clientX;
  layoutState.startLeftWidth = metrics.left;
  layoutState.startMiddleWidth = metrics.middle;
  layoutState.startRightWidth = metrics.right;
  divider.classList.add("active");
  document.body.classList.add("resizing-columns");
  window.addEventListener("pointermove", onDividerPointerMove);
  window.addEventListener("pointerup", stopDividerDrag);
  window.addEventListener("pointercancel", stopDividerDrag);
}

function initWorkspaceResizers() {
  if (!dom.workspace || !dom.dividerLeft || !dom.dividerRight) return;
  dom.dividerLeft.addEventListener("pointerdown", (event) => startDividerDrag(dom.dividerLeft, event));
  dom.dividerRight.addEventListener("pointerdown", (event) => startDividerDrag(dom.dividerRight, event));
  window.addEventListener("resize", syncWorkspaceWidths);
  resetWorkspaceWidths();
}

function getSelectedPlan() {
  if (!appState.actions || !appState.selectedPlanKey) return null;
  return appState.actions.plans.find((plan) => plan.key === appState.selectedPlanKey) || null;
}

function getSelectedSample() {
  if (!appState.rollouts || appState.selectedSampleIndex == null) return null;
  return appState.rollouts.samples.find((sample) => sample.sample_index === appState.selectedSampleIndex) || null;
}

function rootStateTowerById() {
  const towers = appState.actions?.start_state?.towers || [];
  return new Map(towers.map((tower) => [tower.id, tower]));
}

function selectedPlanHighlights() {
  const plan = getSelectedPlan();
  if (!plan) return [];
  const byId = rootStateTowerById();
  const cells = [];
  for (const op of plan.ops || []) {
    if (op.type === 11) {
      cells.push({ x: op.arg0, y: op.arg1, kind: "build", label: "build" });
    } else if (op.type === 21) {
      cells.push({ x: op.arg0, y: op.arg1, kind: "lightning", label: "storm" });
    } else if (op.type === 12 || op.type === 13) {
      const tower = byId.get(op.arg0);
      if (tower) {
        cells.push({
          x: tower.x ?? tower.pos?.x ?? -1,
          y: tower.y ?? tower.pos?.y ?? -1,
          kind: op.type === 12 ? "upgrade" : "downgrade",
          label: op.type === 12 ? "up" : "down",
        });
      }
    }
  }
  return cells.filter((item) => item.x >= 0 && item.y >= 0);
}

function getBoardViewState(boardKey, baseBox) {
  let state = appState.boardViews[boardKey];
  if (!state) {
    state = {
      zoom: 1,
      cx: baseBox.x + baseBox.width / 2,
      cy: baseBox.y + baseBox.height / 2,
    };
    appState.boardViews[boardKey] = state;
  }
  state.baseBox = baseBox;
  return state;
}

function resetBoardView(boardKey, baseBox) {
  appState.boardViews[boardKey] = {
    zoom: 1,
    cx: baseBox.x + baseBox.width / 2,
    cy: baseBox.y + baseBox.height / 2,
    baseBox,
  };
}

function applyBoardView(svg, boardKey, baseBox) {
  const state = getBoardViewState(boardKey, baseBox);
  const width = baseBox.width / state.zoom;
  const height = baseBox.height / state.zoom;
  svg.setAttribute("viewBox", `${state.cx - width / 2} ${state.cy - height / 2} ${width} ${height}`);
}

function attachBoardInteractions(container, svg, boardKey, baseBox) {
  const state = getBoardViewState(boardKey, baseBox);
  container.classList.add("interactive");
  applyBoardView(svg, boardKey, baseBox);
  svg.style.touchAction = "none";

  let dragging = false;
  let lastX = 0;
  let lastY = 0;

  svg.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      state.zoom = Math.max(0.45, Math.min(8, state.zoom * factor));
      applyBoardView(svg, boardKey, baseBox);
    },
    { passive: false }
  );

  svg.addEventListener("pointerdown", (event) => {
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    container.classList.add("dragging");
    svg.setPointerCapture(event.pointerId);
  });

  svg.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    const rect = svg.getBoundingClientRect();
    const vb = svg.viewBox.baseVal;
    const dx = ((event.clientX - lastX) * vb.width) / rect.width;
    const dy = ((event.clientY - lastY) * vb.height) / rect.height;
    state.cx -= dx;
    state.cy -= dy;
    lastX = event.clientX;
    lastY = event.clientY;
    applyBoardView(svg, boardKey, baseBox);
  });

  const stopDragging = () => {
    dragging = false;
    container.classList.remove("dragging");
  };
  svg.addEventListener("pointerup", stopDragging);
  svg.addEventListener("pointercancel", stopDragging);
  svg.addEventListener("pointerleave", stopDragging);

  svg.addEventListener("dblclick", () => {
    resetBoardView(boardKey, baseBox);
    applyBoardView(svg, boardKey, baseBox);
  });
}

function renderBoard(container, rawState, options = {}) {
  container.innerHTML = "";
  const normalized = detectState(rawState);
  if (!normalized) {
    container.textContent = "No board data";
    return;
  }

  const svg = createSvg("svg");
  const defs = createSvg("defs");
  const effectFilter = createSvg("filter");
  effectFilter.setAttribute("id", "effectShadowBlur");
  effectFilter.setAttribute("x", "-35%");
  effectFilter.setAttribute("y", "-35%");
  effectFilter.setAttribute("width", "170%");
  effectFilter.setAttribute("height", "170%");
  const effectBlur = createSvg("feGaussianBlur");
  effectBlur.setAttribute("in", "SourceGraphic");
  effectBlur.setAttribute("stdDeviation", "2.2");
  effectFilter.appendChild(effectBlur);
  defs.appendChild(effectFilter);
  svg.appendChild(defs);
  const layoutRadius = options.layoutRadius || 26;
  const hexRadius = layoutRadius * Math.sqrt(3) / 2;
  const centers = new Map();
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;

  for (const cell of appState.map.cells) {
    const center = centerXY(cell.x, cell.y, layoutRadius);
    centers.set(`${cell.x}:${cell.y}`, center);
    minX = Math.min(minX, center.x - hexRadius - 30);
    maxX = Math.max(maxX, center.x + hexRadius + 30);
    minY = Math.min(minY, center.y - hexRadius - 30);
    maxY = Math.max(maxY, center.y + hexRadius + 30);
  }
  const baseBox = { x: minX, y: minY, width: maxX - minX, height: maxY - minY };

  for (const cell of appState.map.cells) {
    const center = centers.get(`${cell.x}:${cell.y}`);
    const poly = createSvg("polygon");
    poly.setAttribute("points", hexPoints(center.x, center.y, hexRadius));
    poly.setAttribute("fill", terrainColor(cell.terrain));
    poly.setAttribute("stroke", "#8c8c8c");
    poly.setAttribute("stroke-width", "1");
    addTitle(poly, `${cell.x},${cell.y} | ${appState.map.terrain_names[String(cell.terrain)]}`);
    svg.appendChild(poly);
  }

  for (const effect of normalized.effects) {
    const range = effectRange(effect.weaponName);
    if (range <= 0) continue;
    const shadowGroup = createSvg("g");
    shadowGroup.setAttribute("opacity", "0.95");
    for (const cell of appState.map.cells) {
      if (hexDistance(effect.x, effect.y, cell.x, cell.y) > range) continue;
      const center = centers.get(`${cell.x}:${cell.y}`);
      if (!center) continue;
      const poly = createSvg("polygon");
      poly.setAttribute("points", hexPoints(center.x, center.y, hexRadius * 0.96));
      poly.setAttribute("fill", effectColor(effect.weaponName));
      poly.setAttribute("opacity", cell.x === effect.x && cell.y === effect.y ? "0.26" : "0.12");
      poly.setAttribute("filter", "url(#effectShadowBlur)");
      poly.setAttribute("stroke", "none");
      shadowGroup.appendChild(poly);
    }
    addTitle(shadowGroup, `${effect.weaponName} exact range | P${effect.player} | t=${effect.remainingTurns}`);
    svg.appendChild(shadowGroup);
  }

  const slotPlayer = Number(options.slotPlayer ?? dom.playerSelect.value);
  for (const slot of appState.map.slots) {
    if (slot.player !== slotPlayer) continue;
    const center = centers.get(`${slot.x}:${slot.y}`);
    const text = createSvg("text");
    text.setAttribute("x", String(center.x));
    text.setAttribute("y", String(center.y + 7));
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("font-size", "8.4");
    text.setAttribute("font-weight", "700");
    text.setAttribute("fill", playerColor(slot.player));
    text.textContent = slot.name;
    svg.appendChild(text);
  }

  for (const base of appState.map.bases) {
    const center = centers.get(`${base.x}:${base.y}`);
    const circle = createSvg("circle");
    circle.setAttribute("cx", String(center.x));
    circle.setAttribute("cy", String(center.y));
    circle.setAttribute("r", "12");
    circle.setAttribute("fill", "none");
    circle.setAttribute("stroke", playerColor(base.player));
    circle.setAttribute("stroke-width", "3");
    addTitle(circle, `Base P${base.player}`);
    svg.appendChild(circle);

    if (normalized.baseHp[base.player] != null) {
      const text = createSvg("text");
      text.setAttribute("x", String(center.x));
      text.setAttribute("y", String(center.y - 15));
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("font-size", "9");
      text.setAttribute("fill", playerColor(base.player));
      text.textContent = `HP ${normalized.baseHp[base.player]}`;
      svg.appendChild(text);
    }
  }

  for (const effect of normalized.effects) {
    const center = centers.get(`${effect.x}:${effect.y}`);
    if (!center) continue;
    const marker = createSvg("circle");
    marker.setAttribute("cx", String(center.x));
    marker.setAttribute("cy", String(center.y));
    marker.setAttribute("r", String(layoutRadius * 0.48));
    marker.setAttribute("fill", "none");
    marker.setAttribute("stroke", effectColor(effect.weaponName));
    marker.setAttribute("stroke-width", "2.4");
    marker.setAttribute("stroke-dasharray", "6 4");
    marker.setAttribute("opacity", "0.88");
    addTitle(marker, `${effect.weaponName} | P${effect.player} | t=${effect.remainingTurns}`);
    svg.appendChild(marker);
  }

  for (const item of options.highlightCells || []) {
    const center = centers.get(`${item.x}:${item.y}`);
    if (!center) continue;
    const ring = createSvg("circle");
    ring.setAttribute("cx", String(center.x));
    ring.setAttribute("cy", String(center.y));
    ring.setAttribute("r", String(layoutRadius * 0.75));
    ring.setAttribute("fill", "none");
    ring.setAttribute("stroke", highlightColor(item.kind));
    ring.setAttribute("stroke-width", "3.5");
    ring.setAttribute("opacity", "0.95");
    addTitle(ring, `${item.kind} @ (${item.x},${item.y})`);
    svg.appendChild(ring);

    if (item.label) {
      const text = createSvg("text");
      text.setAttribute("x", String(center.x));
      text.setAttribute("y", String(center.y + 4));
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("font-size", "9");
      text.setAttribute("font-weight", "700");
      text.setAttribute("fill", highlightColor(item.kind));
      text.textContent = item.label;
      svg.appendChild(text);
    }
  }

  for (const tower of normalized.towers) {
    const center = centers.get(`${tower.x}:${tower.y}`);
    if (!center) continue;
    const group = createSvg("g");
    const rect = createSvg("rect");
    rect.setAttribute("x", String(center.x - 14));
    rect.setAttribute("y", String(center.y - 14));
    rect.setAttribute("width", "28");
    rect.setAttribute("height", "28");
    rect.setAttribute("rx", "6");
    rect.setAttribute("fill", playerColor(tower.player));
    rect.setAttribute("stroke", "#ffffff");
    rect.setAttribute("stroke-width", "1.8");
    group.appendChild(rect);

    const text = createSvg("text");
    text.setAttribute("x", String(center.x));
    text.setAttribute("y", String(center.y - 1));
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("font-size", "8.8");
    text.setAttribute("font-weight", "700");
    text.setAttribute("fill", "white");
    text.textContent = towerAbbrev(tower.typeName);
    group.appendChild(text);

    const hp = createSvg("text");
    hp.setAttribute("x", String(center.x));
    hp.setAttribute("y", String(center.y + 10));
    hp.setAttribute("text-anchor", "middle");
    hp.setAttribute("font-size", "8");
    hp.setAttribute("fill", "white");
    hp.textContent = `${tower.hp}`;
    group.appendChild(hp);

    addTitle(
      group,
      `Tower #${tower.id} | P${tower.player} | ${tower.typeName} | hp ${tower.hp}/${tower.maxHp} | cd ${tower.cooldown}`
    );
    svg.appendChild(group);
  }

  const antsByCell = new Map();
  for (const ant of normalized.ants) {
    const key = `${ant.x}:${ant.y}`;
    if (!antsByCell.has(key)) antsByCell.set(key, []);
    antsByCell.get(key).push(ant);
  }

  for (const [key, ants] of antsByCell.entries()) {
    const [x, y] = key.split(":").map(Number);
    const center = centers.get(`${x}:${y}`);
    if (!center) continue;
    ants.forEach((ant, index) => {
      const angle = ants.length > 1 ? (Math.PI * 2 * index) / ants.length : 0;
      const offset = ants.length > 1 ? 12 : 0;
      const ax = center.x + Math.cos(angle) * offset;
      const ay = center.y + Math.sin(angle) * offset;
      const group = createSvg("g");

      const circle = createSvg("circle");
      circle.setAttribute("cx", String(ax));
      circle.setAttribute("cy", String(ay));
      circle.setAttribute("r", "10.5");
      circle.setAttribute("fill", "#fffdf8");
      circle.setAttribute("stroke", playerColor(ant.player));
      circle.setAttribute("stroke-width", "2.5");
      group.appendChild(circle);

      const label = createSvg("text");
      label.setAttribute("x", String(ax));
      label.setAttribute("y", String(ay - 1));
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("font-size", "7.6");
      label.setAttribute("font-weight", "700");
      label.setAttribute("fill", playerColor(ant.player));
      label.textContent = antAbbrev(ant.kindName, ant.behaviorName);
      group.appendChild(label);

      const hp = createSvg("text");
      hp.setAttribute("x", String(ax));
      hp.setAttribute("y", String(ay + 8));
      hp.setAttribute("text-anchor", "middle");
      hp.setAttribute("font-size", "7");
      hp.setAttribute("fill", playerColor(ant.player));
      hp.textContent = `${ant.hp}${ant.shield ? `+${ant.shield}` : ""}`;
      group.appendChild(hp);

      addTitle(
        group,
        `Ant #${ant.id} | P${ant.player} | ${ant.kindName} | ${ant.behaviorName} | hp ${ant.hp}/${ant.maxHp} | shield ${ant.shield}`
      );
      svg.appendChild(group);
    });
  }

  container.appendChild(svg);
  attachBoardInteractions(container, svg, options.boardKey || container.id, baseBox);
}

function formatReplayOp(op, perspectivePlayer, replayRound) {
  const type = op.type;
  const pos = op.pos || { x: -1, y: -1 };
  const byId = new Map(
    ((replayRound?.round_start_towers) || (replayRound?.record?.round_state?.towers) || []).map((tower) => [tower.id, tower])
  );
  const slot = (x, y) => slotName(perspectivePlayer, x, y);
  if (type === 11) return `${slot(pos.x, pos.y)}-1`;
  if (type === 12) {
    const tower = byId.get(op.id);
    const head = tower ? slot(perspectivePlayer, tower.pos?.x ?? tower.x, tower.pos?.y ?? tower.y) : `T#${op.id}`;
    return `${head}-U${op.args}`;
  }
  if (type === 13) {
    const tower = byId.get(op.id);
    const head = tower ? slot(perspectivePlayer, tower.pos?.x ?? tower.x, tower.pos?.y ?? tower.y) : `T#${op.id}`;
    return `${head}-5`;
  }
  if (type === 21) return `${slot(pos.x, pos.y)}-6`;
  if (type === 22) return `${slot(pos.x, pos.y)}-EMP`;
  if (type === 23) return `${slot(pos.x, pos.y)}-DEF`;
  if (type === 24) return `${slot(pos.x, pos.y)}-EVA`;
  return JSON.stringify(op);
}

function fullPlanPretty(plan) {
  if (!plan) return "none";
  const first = plan.pretty || "HOLD-0";
  const followup = (plan.followup || "").trim();
  return followup ? `${first} -> ${followup}` : first;
}

function resetStrategyViews() {
  appState.actions = null;
  appState.selectedPlanKey = null;
  appState.rollouts = null;
  appState.selectedSampleIndex = null;
  appState.trace = null;
  appState.selectedTraceStep = 0;
  appState.boardMode = "replay";

  dom.actionsSummary.textContent = "尚未计算候选行动。";
  dom.actionsSummary.classList.add("empty-box");
  $("actionsTable").querySelector("tbody").innerHTML = "";

  dom.samplesMeta.textContent = "";
  $("samplesTable").querySelector("tbody").innerHTML = "";

  dom.traceMeta.textContent = "";
  dom.traceEval.textContent = "尚未选择 rollout sample。";
  dom.traceEval.classList.add("empty-box");
  dom.traceStepTabs.innerHTML = "";
  dom.traceStepMeta.textContent = "尚未载入 trace。";
  dom.traceStepMeta.classList.add("empty-box");
  dom.movesMeta.textContent = "";
  $("movesTable").querySelector("tbody").innerHTML = "";
  dom.traceStartHeader.textContent = "";
  dom.traceStartMeta.textContent = "尚未载入 trace。";
  dom.traceStartMeta.classList.add("empty-box");
  dom.traceStartBoard.innerHTML = "";
  dom.traceEndBoard.innerHTML = "";

  dom.strategyMeta.textContent = "";
  dom.replayRootSummary.textContent = "尚未计算 root 候选。";
  dom.replayRootSummary.classList.add("empty-box");
  dom.rootSourceSummary.textContent = "尚未载入独立候选。";
  dom.rootSourceSummary.classList.add("empty-box");
  dom.selectedActionInfo.textContent = "尚未选中 action。";
  dom.selectedActionInfo.classList.add("empty-box");

  renderUnifiedBoard();
}

function renderBoardModeTabs() {
  const modes = [{ key: "replay", label: "Replay" }];
  if (appState.actions) modes.push({ key: "root", label: "Root" });
  if (appState.actions && getSelectedPlan()) modes.push({ key: "action", label: "Action" });
  if (!modes.some((item) => item.key === appState.boardMode)) {
    appState.boardMode = modes[modes.length - 1].key;
  }

  dom.boardViewTabs.innerHTML = "";
  for (const mode of modes) {
    const button = document.createElement("button");
    button.textContent = mode.label;
    if (mode.key === appState.boardMode) button.classList.add("active");
    button.addEventListener("click", () => {
      appState.boardMode = mode.key;
      renderUnifiedBoard();
    });
    dom.boardViewTabs.appendChild(button);
  }
}

function resolveUnifiedBoardModel() {
  const selectedPlan = getSelectedPlan();
  if (appState.boardMode === "action" && appState.actions) {
    return {
      header: selectedPlan ? `Selected action | ${fullPlanPretty(selectedPlan)}` : "Selected action",
      state: appState.trace?.trace?.rounds?.[0]?.trace?.state_start || appState.actions.start_state,
      meta: selectedPlan
        ? `Action preview of <code>${fullPlanPretty(selectedPlan)}</code>. Highlight rings mark current-turn operations.`
        : "No action selected.",
      highlights: selectedPlanHighlights(),
    };
  }
  if (appState.boardMode === "root" && appState.actions) {
    const counts = appState.actions.root_plan_counts;
    return {
      header: `Root state | serial ${appState.actions.serial}`,
      state: appState.actions.start_state,
      meta: `base ${counts.base_count} | lure ${counts.lure_count} | lightning ${counts.lightning_count} | raw ${counts.raw_plan_count} | unique ${counts.unique_plan_count}`,
      highlights: [],
    };
  }
  if (appState.replayRound) {
    const { round, record, full_round_state } = appState.replayRound;
    const state = full_round_state || record.round_state || {};
    const camps = state.camps || state.camps_hp || [null, null];
    const coins = state.coins || [null, null];
    return {
      header: `Replay round ${round}`,
      state,
      meta: `coins ${coins.join(" / ")} | camps ${camps.join(" / ")}`,
      highlights: [],
    };
  }
  return {
    header: "",
    state: null,
    meta: "尚未载入盘面。",
    highlights: [],
  };
}

function renderUnifiedBoard() {
  renderBoardModeTabs();
  const model = resolveUnifiedBoardModel();
  const selectedPlan = getSelectedPlan();
  dom.unifiedBoardHeader.textContent = model.header;
  if (!model.state) {
    dom.unifiedBoard.innerHTML = "";
    dom.unifiedBoardMeta.textContent = model.meta;
    dom.unifiedBoardMeta.classList.add("empty-box");
    dom.selectedActionInfo.textContent = selectedPlan ? fullPlanPretty(selectedPlan) : "尚未选中 action。";
    dom.selectedActionInfo.classList.toggle("empty-box", !selectedPlan);
    return;
  }
  renderBoard(dom.unifiedBoard, model.state, {
    boardKey: "unifiedBoard",
    slotPlayer: Number(dom.playerSelect.value),
    highlightCells: model.highlights,
    layoutRadius: 26,
  });
  dom.unifiedBoardMeta.innerHTML = model.meta;
  dom.unifiedBoardMeta.classList.remove("empty-box");
  if (selectedPlan) {
    const threat =
      (selectedPlan.mean_rollout.terminal.worker_threat_raw || 0) +
      (selectedPlan.mean_rollout.terminal.combat_threat_raw || 0);
    dom.selectedActionInfo.innerHTML = `
      action <code>${fullPlanPretty(selectedPlan)}</code> |
      total ${formatNumber(selectedPlan.mean_score)} |
      rollout ${formatNumber(selectedPlan.mean_rollout_score)} |
      heuristic ${formatNumber(selectedPlan.heuristic)} |
      threat ${formatNumber(threat)}
    `;
    dom.selectedActionInfo.classList.remove("empty-box");
  } else {
    dom.selectedActionInfo.textContent = "尚未选中 action。";
    dom.selectedActionInfo.classList.add("empty-box");
  }
}

function renderReplayRound() {
  if (!appState.replayRound) return;
  const { record, round, full_round_state } = appState.replayRound;
  const state = full_round_state || record.round_state || {};
  const camps = state.camps || state.camps_hp || [null, null];
  const coins = state.coins || [null, null];
  dom.replayRoundMeta.textContent = `round ${round} | seed ${appState.replayRound.seed} | coins ${coins.join(" / ")} | camps ${camps.join(" / ")}`;
  dom.replayOps0.innerHTML =
    (record.op0 || []).map((op) => formatReplayOp(op, 0, appState.replayRound)).join("<br>") || "<span class='empty-box'>HOLD</span>";
  dom.replayOps1.innerHTML =
    (record.op1 || []).map((op) => formatReplayOp(op, 1, appState.replayRound)).join("<br>") || "<span class='empty-box'>HOLD</span>";
  renderUnifiedBoard();
}

function renderRootSummary() {
  if (!appState.actions) {
    dom.replayRootSummary.textContent = "尚未计算 root 候选。";
    dom.replayRootSummary.classList.add("empty-box");
    dom.rootSourceSummary.textContent = "尚未载入独立候选。";
    dom.rootSourceSummary.classList.add("empty-box");
    return;
  }
  const best = appState.actions.plans?.[0];
  const selected = getSelectedPlan();
  dom.replayRootSummary.classList.remove("empty-box");
  dom.replayRootSummary.innerHTML = `
    best <code>${fullPlanPretty(best)}</code> = ${formatNumber(best?.mean_score)} |
    selected <code>${fullPlanPretty(selected)}</code> |
    board mode <code>${appState.boardMode}</code>
  `;

  const sources = appState.actions.root_plan_sources || {};
  const formatSource = (title, items) => {
    const rows = (items || []).map((item) => `${item.name}: ${fullPlanPretty(item)}`);
    return `<strong>${title}</strong><br>${rows.length ? rows.join("<br>") : "<span class='empty-box'>none</span>"}`;
  };
  dom.rootSourceSummary.classList.remove("empty-box");
  dom.rootSourceSummary.innerHTML = [
    formatSource("Base", sources.base),
    formatSource("Lure", sources.lure),
    formatSource("L-P", sources.lightning_prep),
    formatSource("L-C", sources.lightning_center),
  ].join("<br><br>");
}

function renderActions() {
  const tbody = $("actionsTable").querySelector("tbody");
  tbody.innerHTML = "";
  if (!appState.actions) {
    renderRootSummary();
    renderUnifiedBoard();
    return;
  }
  dom.strategyMeta.textContent = `reconstructed root state | serial ${appState.actions.serial}`;
  const counts = appState.actions.root_plan_counts;
  dom.actionsSummary.classList.remove("empty-box");
  dom.actionsSummary.textContent =
    `base ${counts.base_count} | lure ${counts.lure_count} | lightning ${counts.lightning_count} | raw ${counts.raw_plan_count} | unique ${counts.unique_plan_count}`;

  appState.actions.plans.forEach((plan, index) => {
    const row = document.createElement("tr");
    if (plan.key === appState.selectedPlanKey) row.classList.add("selected");
    const threat = (plan.mean_rollout.terminal.worker_threat_raw || 0) + (plan.mean_rollout.terminal.combat_threat_raw || 0);
    row.innerHTML = `
      <td>${index + 1}</td>
      <td>${fullPlanPretty(plan)}</td>
      <td>${formatPlainNumber(plan.mean_rollout_score, 2)}</td>
      <td>${formatNumber(plan.heuristic)}</td>
      <td>${formatNumber(plan.mean_rollout.terminal.base_hp_raw)}</td>
      <td>${formatNumber(plan.mean_rollout.terminal.money_raw)}</td>
      <td>${formatNumber(threat)}</td>
    `;
    row.addEventListener("click", () => selectPlan(plan.key));
    tbody.appendChild(row);
  });
  renderRootSummary();
  renderUnifiedBoard();
}

function renderSamples() {
  const tbody = $("samplesTable").querySelector("tbody");
  tbody.innerHTML = "";
  if (!appState.rollouts) return;
  dom.samplesMeta.textContent = `${fullPlanPretty(appState.rollouts.plan)} | ${appState.rollouts.samples.length} samples`;
  const sortedSamples = [...appState.rollouts.samples].sort((lhs, rhs) => {
    const lhsWeight = sampleWeight(lhs);
    const rhsWeight = sampleWeight(rhs);
    if (lhsWeight !== rhsWeight) return rhsWeight - lhsWeight;
    return lhs.sample_index - rhs.sample_index;
  });
  sortedSamples.forEach((sample) => {
    const row = document.createElement("tr");
    if (sample.sample_index === appState.selectedSampleIndex) row.classList.add("selected");
    const terminal = sample.terminal;
    const moveCount = (sample.first_round_move_assignments || []).length;
    const threat = (terminal.worker_threat_raw || 0) + (terminal.combat_threat_raw || 0);
    const normalizedWeight = sampleWeight(sample);
    row.innerHTML = `
      <td>${sample.sample_index}</td>
      <td>${formatPlainNumber(sample.total_score, 2)}</td>
      <td>${formatPlainNumber(normalizedWeight, 4)}</td>
      <td>${formatNumber(terminal.base_hp_raw)}</td>
      <td>${formatNumber(terminal.money_raw)}</td>
      <td>${formatNumber(threat)}</td>
      <td>${moveCount}</td>
    `;
    row.addEventListener("click", () => selectSample(sample.sample_index));
    tbody.appendChild(row);
  });
}

function renderTracePanels() {
  if (!appState.trace) {
    dom.traceStartBoard.innerHTML = "";
    dom.traceEndBoard.innerHTML = "";
    return;
  }

  const trace = appState.trace.trace;
  dom.traceMeta.textContent = `${fullPlanPretty(appState.trace.plan)} | sample ${trace.sample_index} | seed ${trace.seed}`;
  dom.traceEval.classList.remove("empty-box");
  dom.traceEval.innerHTML = `
    total ${formatNumber(trace.total_score)} |
    lightning ${formatNumber(trace.lightning_bonus_score)} |
    baseHP ${formatNumber(trace.terminal.base_hp_raw)} |
    tower ${formatNumber(trace.terminal.tower_value_raw)} |
    money ${formatNumber(trace.terminal.money_raw)} |
    workerThreat ${formatNumber(trace.terminal.worker_threat_raw)} |
    combatThreat ${formatNumber(trace.terminal.combat_threat_raw)}
  `;

  dom.traceStepTabs.innerHTML = "";
  trace.rounds.forEach((round, index) => {
    const button = document.createElement("button");
    button.textContent = `Step ${index}`;
    if (index === appState.selectedTraceStep) button.classList.add("active");
    button.addEventListener("click", () => {
      appState.selectedTraceStep = index;
      renderTracePanels();
      renderMovesTable();
    });
    dom.traceStepTabs.appendChild(button);
  });

  const step = trace.rounds[appState.selectedTraceStep];
  if (!step) return;

  dom.traceStartHeader.textContent = `step ${appState.selectedTraceStep} | ${step.phase}`;
  renderBoard(dom.traceStartBoard, step.trace.state_start, {
    boardKey: "traceStartBoard",
    slotPlayer: Number(dom.playerSelect.value),
    layoutRadius: 22,
  });
  renderBoard(dom.traceEndBoard, step.trace.state_end, {
    boardKey: "traceEndBoard",
    slotPlayer: Number(dom.playerSelect.value),
    layoutRadius: 22,
  });

  dom.traceStartMeta.classList.remove("empty-box");
  dom.traceStartMeta.innerHTML = `ops <code>${step.applied_operations_pretty || "HOLD-0"}</code> | move path prob ${formatNumber(
    step.trace.move_path_probability
  )}`;

  dom.traceStepMeta.classList.remove("empty-box");
  dom.traceStepMeta.innerHTML = `phase ${step.phase} | move count ${(step.trace.move_assignments || []).length} | action preview is also available in Unified Board / Action`;
  renderUnifiedBoard();
}

function renderMovesTable() {
  const tbody = $("movesTable").querySelector("tbody");
  tbody.innerHTML = "";
  if (!appState.trace) return;
  const step = appState.trace.trace.rounds[appState.selectedTraceStep];
  if (!step) return;

  const rows = step.trace.move_assignments || [];
  dom.movesMeta.textContent = `step ${appState.selectedTraceStep} | ${rows.length} assignments`;
  if (rows.length === 0) {
    const row = document.createElement("tr");
    row.innerHTML = `<td colspan="7">No ant movement in this simulated round.</td>`;
    tbody.appendChild(row);
    return;
  }

  rows.forEach((move) => {
    const before = move.ant_before || {};
    const options = (move.options || [])
      .slice(0, 3)
      .map((option) => `${option.direction}@(${option.nx},${option.ny}) p=${formatNumber(option.probability)}`)
      .join("<br>");
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${before.id}</td>
      <td>${before.kind_name || before.kindName || ""}/${before.behavior_name || before.behaviorName || ""}</td>
      <td>(${before.x},${before.y}) hp ${before.hp}</td>
      <td>${move.chosen_direction}</td>
      <td>${formatNumber(move.chosen_probability)}</td>
      <td>${move.choice_source}</td>
      <td>${options}</td>
    `;
    tbody.appendChild(row);
  });
}

async function loadReplay() {
  try {
    setStatus("Loading replay...");
    cancelScheduledRoundLoad();
    resetStrategyViews();
    const replayPath = dom.replayPath.value.trim();
    appState.replayMeta = await postJSON("/api/replay/load", { replay_path: replayPath });
    const maxRound = Math.max(0, appState.replayMeta.round_count - 1);
    dom.roundInput.max = String(maxRound);
    dom.roundSlider.max = String(maxRound);
    const round = clampRound(Number(dom.roundInput.value || 0));
    dom.roundInput.value = String(round);
    dom.roundSlider.value = String(round);
    await loadRound();
    setStatus("Replay loaded");
  } catch (err) {
    setStatus(String(err), true);
  }
}

async function loadRound(targetRound = null) {
  if (!appState.replayMeta) return;
  cancelScheduledRoundLoad();
  const round = syncRoundControls(targetRound ?? Number(dom.roundInput.value || 0));
  const requestSerial = ++roundLoadState.requestSerial;
  try {
    setStatus("Loading round...");
    resetStrategyViews();
    const replayRound = await postJSON("/api/replay/round", {
      replay_path: dom.replayPath.value.trim(),
      round,
    });
    if (requestSerial !== roundLoadState.requestSerial) return;
    appState.replayRound = replayRound;
    appState.boardMode = "replay";
    renderReplayRound();
    renderRootSummary();
    setStatus(`Round ${round} loaded`);
  } catch (err) {
    if (requestSerial !== roundLoadState.requestSerial) return;
    setStatus(String(err), true);
  }
}

async function computeActions() {
  if (!appState.replayMeta) return;
  try {
    setStatus("Computing actions...");
    appState.actions = await postJSON("/api/inspect/actions", {
      replay_path: dom.replayPath.value.trim(),
      round: Number(dom.roundInput.value || 0),
      player: Number(dom.playerSelect.value || 0),
      rollout_count: STRATEGY_ROLLOUT_COUNT,
    });
    appState.selectedPlanKey = appState.actions.plans[0]?.key || null;
    appState.boardMode = "root";
    renderActions();
    if (appState.selectedPlanKey) {
      await loadRollouts();
    }
    setStatus("Actions computed");
  } catch (err) {
    setStatus(String(err), true);
  }
}

async function selectPlan(planKey) {
  appState.selectedPlanKey = planKey;
  appState.boardMode = "action";
  renderActions();
  await loadRollouts();
}

async function loadRollouts() {
  if (!appState.selectedPlanKey) return;
  try {
    setStatus("Computing rollout samples...");
    appState.rollouts = await postJSON("/api/inspect/rollouts", {
      replay_path: dom.replayPath.value.trim(),
      round: Number(dom.roundInput.value || 0),
      player: Number(dom.playerSelect.value || 0),
      plan_key: appState.selectedPlanKey,
      rollout_count: STRATEGY_ROLLOUT_COUNT,
      sample_count: STRATEGY_ROLLOUT_COUNT,
    });
    const bestSample = [...(appState.rollouts.samples || [])].sort((lhs, rhs) => {
      const lhsWeight = sampleWeight(lhs);
      const rhsWeight = sampleWeight(rhs);
      if (lhsWeight !== rhsWeight) return rhsWeight - lhsWeight;
      return lhs.sample_index - rhs.sample_index;
    })[0];
    appState.selectedSampleIndex = bestSample?.sample_index ?? 0;
    renderSamples();
    await loadTrace();
    setStatus("Rollout samples ready");
  } catch (err) {
    setStatus(String(err), true);
  }
}

async function selectSample(sampleIndex) {
  appState.selectedSampleIndex = sampleIndex;
  renderSamples();
  await loadTrace();
}

async function loadTrace() {
  if (appState.selectedPlanKey == null || appState.selectedSampleIndex == null) return;
  try {
    setStatus("Computing rollout trace...");
    appState.trace = await postJSON("/api/inspect/trace", {
      replay_path: dom.replayPath.value.trim(),
      round: Number(dom.roundInput.value || 0),
      player: Number(dom.playerSelect.value || 0),
      plan_key: appState.selectedPlanKey,
      rollout_count: STRATEGY_ROLLOUT_COUNT,
      sample_index: appState.selectedSampleIndex,
      sample_count: Math.max(1, appState.rollouts?.samples?.length || 0),
    });
    appState.selectedTraceStep = 0;
    renderTracePanels();
    renderMovesTable();
    setStatus("Trace ready");
  } catch (err) {
    setStatus(String(err), true);
  }
}

async function init() {
  Object.assign(dom, {
    statusText: $("statusText"),
    workspace: document.querySelector(".workspace"),
    replayPath: $("replayPath"),
    playerSelect: $("playerSelect"),
    roundInput: $("roundInput"),
    roundSlider: $("roundSlider"),
    columnLeft: document.querySelector(".column-left"),
    columnMiddle: document.querySelector(".column-middle"),
    dividerLeft: $("dividerLeft"),
    dividerRight: $("dividerRight"),
    unifiedBoard: $("unifiedBoard"),
    unifiedBoardHeader: $("unifiedBoardHeader"),
    unifiedBoardMeta: $("unifiedBoardMeta"),
    selectedActionInfo: $("selectedActionInfo"),
    boardViewTabs: $("boardViewTabs"),
    replayOps0: $("replayOps0"),
    replayOps1: $("replayOps1"),
    replayRoundMeta: $("replayRoundMeta"),
    replayRootSummary: $("replayRootSummary"),
    rootSourceSummary: $("rootSourceSummary"),
    strategyMeta: $("strategyMeta"),
    actionsSummary: $("actionsSummary"),
    samplesMeta: $("samplesMeta"),
    traceMeta: $("traceMeta"),
    traceEval: $("traceEval"),
    traceStepTabs: $("traceStepTabs"),
    traceStartBoard: $("traceStartBoard"),
    traceEndBoard: $("traceEndBoard"),
    traceStartHeader: $("traceStartHeader"),
    traceStartMeta: $("traceStartMeta"),
    traceStepMeta: $("traceStepMeta"),
    movesMeta: $("movesMeta"),
  });

  try {
    setStatus("Loading map...");
    appState.map = await getJSON("/api/map");
    buildSlotLookups();
    initWorkspaceResizers();
    dom.roundSlider.addEventListener("input", () => {
      syncRoundControls(Number(dom.roundSlider.value || 0));
      scheduleRoundLoad();
    });
    dom.roundInput.addEventListener("input", () => {
      dom.roundSlider.value = dom.roundInput.value;
    });
    dom.roundInput.addEventListener("change", () => {
      loadRound(Number(dom.roundInput.value || 0));
    });
    $("loadReplayBtn").addEventListener("click", loadReplay);
    $("computeActionsBtn").addEventListener("click", computeActions);
    dom.playerSelect.addEventListener("change", () => {
      renderReplayRound();
      renderActions();
      renderTracePanels();
      renderMovesTable();
    });
    await loadReplay();
  } catch (err) {
    setStatus(String(err), true);
  }
}

window.addEventListener("load", init);
