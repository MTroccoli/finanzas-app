/* ============================================================
   BIT BROS — platformer clásico en Canvas 2D, sin dependencias.
   ============================================================ */

const TILE = 32;
const CANVAS_W = 800;
const CANVAS_H = 480;

const GRAVITY = 0.5;
const MAX_FALL = 15;
const MOVE_ACCEL = 0.7;
const MAX_SPEED = 4.4;
const AIR_ACCEL = 0.5;
const FRICTION = 0.78;
const JUMP_VELOCITY = -12.8; // generous jump (~5 tiles of height) so every platform in the levels is reachable
const JUMP_CUT = 0.5;
const STOMP_BOUNCE = -8.5;
const STOMP_TOLERANCE = 14;
const INVULN_TIME = 1500;
const LEVEL_TIME = 400;

const JUMP_BUFFER_MS = 140;   // a jump press is remembered briefly so a tap never gets lost to frame timing
const COYOTE_MS = 90;         // short grace window to jump after walking off a ledge
const SHOOT_COOLDOWN_MS = 400;
const FIREBALL_SPEED = 6.5;
const FIREBALL_GRAVITY = 0.5;
const FIREBALL_LIFESPAN_MS = 2500;
const MUSHROOM_SCORE = 1000;
const FLOWER_SCORE = 1000;

const SIZES = {
  small: { w: 22, h: 30 },
  big: { w: 24, h: 40 },
  fire: { w: 24, h: 40 },
};

// ---------------------------------------------------------------
// Level builder: programmatic spec -> tile grid + entity lists
// ---------------------------------------------------------------
function buildLevel(spec) {
  const { width, height, groundY, pits = [], platforms = [], coins = [],
          goombas = [], mushrooms = [], flowers = [], flag, spawn, name } = spec;

  const solid = Array.from({ length: height }, () => new Array(width).fill(false));

  for (let y = groundY; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const inPit = pits.some(([a, b]) => x >= a && x <= b);
      if (!inPit) solid[y][x] = true;
    }
  }

  for (const p of platforms) {
    for (let i = 0; i < p.w; i++) solid[p.y][p.x + i] = true;
  }

  return {
    name,
    width, height, groundY,
    solid,
    coins: coins.map(([x, y]) => ({ x: x * TILE + TILE / 2, y: y * TILE + TILE / 2, taken: false })),
    goombas: goombas.map(g => ({
      x: g.x * TILE, y: g.y * TILE - 24,
      w: 26, h: 24,
      minX: g.range[0] * TILE, maxX: g.range[1] * TILE,
      vx: 1.2, alive: true, squash: 0,
    })),
    mushrooms: mushrooms.map(([x, row]) => ({
      x: x * TILE, y: row * TILE - 22, w: 24, h: 22, taken: false,
    })),
    flowers: flowers.map(([x, row]) => ({
      x: x * TILE, y: row * TILE - 24, w: 22, h: 24, taken: false,
    })),
    villain: spec.villain ? {
      x: spec.villain.x * TILE, y: spec.villain.y * TILE - 42,
      w: 30, h: 42,
      minX: spec.villain.range[0] * TILE, maxX: spec.villain.range[1] * TILE,
      vx: 1.4, alive: true, hp: spec.villain.hp ?? 3, hitUntil: 0,
    } : null,
    flag: { x: flag.x * TILE + TILE / 2, y: (groundY) * TILE, topY: flag.y * TILE },
    spawn: { x: spawn.x * TILE, y: spawn.y * TILE },
    pixelWidth: width * TILE,
    pixelHeight: height * TILE,
  };
}

const LEVEL_SPECS = [
  {
    name: '1-1',
    width: 70, height: 15, groundY: 13,
    pits: [[18, 20], [40, 42]],
    // Platforms sit 4 tiles above the ground (clearing a running player's
    // head, well within the jump's ~5-tile max height) and are spaced with
    // at least 5 clear tiles of runway on both sides so a jump never clips
    // a neighboring pit or platform mid-arc.
    platforms: [
      { x: 8, y: 9, w: 3 },
      { x: 30, y: 9, w: 3 },
      { x: 55, y: 9, w: 3 },
    ],
    coins: [
      [9, 8], [10, 8],
      [31, 8],
      [56, 8], [57, 8],
      [14, 12], [24, 12], [36, 12], [48, 12], [62, 12],
    ],
    goombas: [
      { x: 12, y: 13, range: [10, 17] },
      { x: 25, y: 13, range: [23, 39] },
      { x: 46, y: 13, range: [43, 51] },
      { x: 58, y: 13, range: [55, 66] },
    ],
    mushrooms: [[6, 13]],
    flowers: [[31, 9]],
    flag: { x: 66, y: 3 },
    spawn: { x: 2, y: 11 },
  },
  {
    name: '1-2',
    width: 85, height: 15, groundY: 13,
    pits: [[10, 11], [24, 26], [38, 39], [55, 58], [70, 71]],
    // Platforms sit 4 tiles above the ground (clearing a running player's
    // head, well within the jump's ~5-tile max height) and are spaced with
    // at least 5 clear tiles of runway on both sides so a jump never clips
    // a neighboring pit or platform mid-arc.
    platforms: [
      { x: 16, y: 9, w: 3 },
      { x: 46, y: 9, w: 3 },
      { x: 63, y: 9, w: 3 },
    ],
    coins: [
      [17, 8],
      [47, 8],
      [64, 8], [65, 8],
      [3, 12], [20, 12], [33, 12], [52, 12], [67, 12], [79, 12],
    ],
    goombas: [
      { x: 6, y: 13, range: [3, 9] },
      { x: 16, y: 13, range: [13, 22] },
      { x: 30, y: 13, range: [28, 36] },
      { x: 44, y: 13, range: [41, 53] },
      { x: 62, y: 13, range: [60, 68] },
      { x: 78, y: 13, range: [74, 83] },
    ],
    mushrooms: [[3, 13]],
    flowers: [[47, 9]],
    flag: { x: 82, y: 3 },
    spawn: { x: 2, y: 11 },
  },
  {
    name: '1-3',
    width: 100, height: 15, groundY: 13,
    pits: [[9, 10], [20, 22], [33, 34], [44, 47], [58, 60], [72, 74], [88, 90]],
    // Platforms sit 4 tiles above the ground (clearing a running player's
    // head, well within the jump's ~5-tile max height) and are spaced with
    // at least 2-3 clear tiles of runway on both sides so a jump never clips
    // a neighboring pit or platform mid-arc.
    platforms: [
      { x: 15, y: 9, w: 3 },
      { x: 27, y: 9, w: 3 },
      { x: 38, y: 9, w: 3 },
      { x: 52, y: 9, w: 3 },
      { x: 65, y: 9, w: 3 },
      { x: 80, y: 9, w: 4 },
    ],
    coins: [
      [16, 8],
      [28, 8],
      [39, 8],
      [53, 8], [54, 8],
      [66, 8],
      [81, 8], [82, 8],
      [5, 12], [24, 12], [42, 12], [56, 12], [70, 12], [85, 12],
    ],
    goombas: [
      { x: 6, y: 13, range: [3, 8] },
      { x: 16, y: 13, range: [13, 19] },
      { x: 27, y: 13, range: [24, 31] },
      { x: 39, y: 13, range: [36, 42] },
      { x: 53, y: 13, range: [49, 56] },
      { x: 65, y: 13, range: [62, 70] },
      { x: 80, y: 13, range: [76, 86] },
    ],
    mushrooms: [[3, 13]],
    flowers: [[28, 9]],
    villain: { x: 95, y: 13, range: [92, 98], hp: 3 },
    flag: { x: 97, y: 3 },
    spawn: { x: 2, y: 11 },
  },
];

// ---------------------------------------------------------------
// Input
// ---------------------------------------------------------------
const keys = { left: false, right: false, jump: false, shoot: false };

// Jump/shoot presses are buffered by timestamp (not sampled per-frame), so a
// quick tap always registers even if it happens to fall between two frames.
let jumpBufferUntil = 0;
let shootBufferUntil = 0;
let coyoteUntil = 0;
let lastShotAt = -Infinity;

function requestJump() { jumpBufferUntil = performance.now() + JUMP_BUFFER_MS; }
function requestShoot() { shootBufferUntil = performance.now() + JUMP_BUFFER_MS; }

window.addEventListener('keydown', e => {
  if (['ArrowLeft', 'KeyA'].includes(e.code)) keys.left = true;
  if (['ArrowRight', 'KeyD'].includes(e.code)) keys.right = true;
  if (['ArrowUp', 'KeyW', 'Space'].includes(e.code)) { keys.jump = true; requestJump(); }
  if (['KeyX', 'ShiftLeft', 'ShiftRight'].includes(e.code)) { keys.shoot = true; requestShoot(); }
  if (e.code === 'KeyR') restartGame();
  if (['Space', 'ArrowUp'].includes(e.code)) e.preventDefault();
});
window.addEventListener('keyup', e => {
  if (['ArrowLeft', 'KeyA'].includes(e.code)) keys.left = false;
  if (['ArrowRight', 'KeyD'].includes(e.code)) keys.right = false;
  if (['ArrowUp', 'KeyW', 'Space'].includes(e.code)) keys.jump = false;
  if (['KeyX', 'ShiftLeft', 'ShiftRight'].includes(e.code)) keys.shoot = false;
});

// Pointer Events unify touch/mouse/pen with a single listener set and, via
// setPointerCapture, keep tracking the press even if the finger slides off
// the button — this is what was causing left/right/jump to randomly "not work".
function bindButton(id, onDown, onUp) {
  const el = document.getElementById(id);
  const down = e => { e.preventDefault(); el.setPointerCapture?.(e.pointerId); onDown(); };
  const up = e => { e.preventDefault(); onUp(); };
  el.addEventListener('pointerdown', down);
  el.addEventListener('pointerup', up);
  el.addEventListener('pointercancel', up);
  el.addEventListener('contextmenu', e => e.preventDefault());
}
bindButton('btn-left', () => keys.left = true, () => keys.left = false);
bindButton('btn-right', () => keys.right = true, () => keys.right = false);
bindButton('btn-jump', () => { keys.jump = true; requestJump(); }, () => keys.jump = false);
bindButton('btn-shoot', () => { keys.shoot = true; requestShoot(); }, () => keys.shoot = false);

// ---------------------------------------------------------------
// Game state
// ---------------------------------------------------------------
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');

const hud = {
  score: document.getElementById('hud-score'),
  coins: document.getElementById('hud-coins'),
  lives: document.getElementById('hud-lives'),
  level: document.getElementById('hud-level'),
  time: document.getElementById('hud-time'),
};
const overlay = document.getElementById('overlay');
const overlayTitle = document.getElementById('overlay-title');
const overlayMsg = document.getElementById('overlay-msg');
const overlayBtn = document.getElementById('overlay-btn');

let state = 'start'; // start | playing | levelcomplete | win | gameover
let levelIndex = 0;
let level = null;
let player = null;
let camera = { x: 0 };
let score = 0;
let coinsCollected = 0;
let lives = 3;
let timeLeft = LEVEL_TIME;
let timeAccum = 0;
let invulnUntil = 0;
let stateTimer = 0;
let frameTime = 0;
let currentPowerState = 'small'; // small | big | fire — carries over between levels, resets on death
let fireballs = [];

function newPlayer(spawn, powerState = 'small') {
  const size = SIZES[powerState];
  return {
    x: spawn.x, y: spawn.y, w: size.w, h: size.h,
    vx: 0, vy: 0, onGround: false, facing: 1, dead: false,
    powerState,
  };
}

function setPowerState(newState) {
  if (player.powerState === newState) return;
  const oldH = player.h;
  const size = SIZES[newState];
  player.w = size.w;
  player.h = size.h;
  player.y += oldH - size.h; // keep feet planted when growing/shrinking
  player.powerState = newState;
  currentPowerState = newState;
}

function spawnFireball() {
  fireballs.push({
    x: player.facing > 0 ? player.x + player.w : player.x - 10,
    y: player.y + player.h * 0.55,
    vx: FIREBALL_SPEED * player.facing,
    vy: 2,
    r: 7,
    bornAt: performance.now(),
    alive: true,
  });
}

function updateFireballs(dt) {
  for (const fb of fireballs) {
    if (!fb.alive) continue;
    fb.vy += FIREBALL_GRAVITY * dt;
    fb.x += fb.vx * dt;
    fb.y += fb.vy * dt;

    if (performance.now() - fb.bornAt > FIREBALL_LIFESPAN_MS) { fb.alive = false; continue; }
    if (fb.y > level.pixelHeight + 60) { fb.alive = false; continue; }

    if (fb.vy > 0 && isSolidTile(Math.floor(fb.x / TILE), Math.floor((fb.y + fb.r) / TILE))) {
      fb.y = Math.floor((fb.y + fb.r) / TILE) * TILE - fb.r;
      fb.vy = -Math.abs(fb.vy) * 0.7 - 3;
    }
    const leadTx = Math.floor((fb.x + (fb.vx > 0 ? fb.r : -fb.r)) / TILE);
    if (isSolidTile(leadTx, Math.floor(fb.y / TILE))) { fb.alive = false; continue; }

    for (const g of level.goombas) {
      if (!g.alive) continue;
      if (fb.x + fb.r > g.x && fb.x - fb.r < g.x + g.w && fb.y + fb.r > g.y && fb.y - fb.r < g.y + g.h) {
        g.alive = false;
        fb.alive = false;
        score += 100;
        hud.score.textContent = score;
        break;
      }
    }

    const v = level.villain;
    if (fb.alive && v && v.alive && Date.now() >= v.hitUntil &&
        fb.x + fb.r > v.x && fb.x - fb.r < v.x + v.w && fb.y + fb.r > v.y && fb.y - fb.r < v.y + v.h) {
      fb.alive = false;
      damageVillain();
    }
  }
  fireballs = fireballs.filter(fb => fb.alive);
}

function loadLevel(idx) {
  levelIndex = idx;
  level = buildLevel(LEVEL_SPECS[idx]);
  player = newPlayer(level.spawn, currentPowerState);
  camera.x = 0;
  timeLeft = LEVEL_TIME;
  timeAccum = 0;
  fireballs = [];
  hud.level.textContent = level.name;
}

function startGame() {
  score = 0; coinsCollected = 0; lives = 3;
  currentPowerState = 'small';
  loadLevel(0);
  state = 'playing';
  overlay.classList.add('hidden');
}

function restartGame() {
  if (state === 'start') return;
  startGame();
}

overlayBtn.addEventListener('click', () => {
  if (state === 'start' || state === 'gameover' || state === 'win') startGame();
});

// ---------------------------------------------------------------
// Collision helpers
// ---------------------------------------------------------------
function isSolidTile(tx, ty) {
  if (ty < 0) return false;
  if (ty >= level.height) return false; // below the map: open pit, falling here should kill the player
  if (tx < 0 || tx >= level.width) return true; // treat OOB sides as solid walls
  return level.solid[ty][tx];
}

function aabbOverlap(a, b) {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

function rectTiles(x, y, w, h) {
  const tiles = [];
  const tx0 = Math.floor(x / TILE), tx1 = Math.floor((x + w - 1) / TILE);
  const ty0 = Math.floor(y / TILE), ty1 = Math.floor((y + h - 1) / TILE);
  for (let ty = ty0; ty <= ty1; ty++) {
    for (let tx = tx0; tx <= tx1; tx++) {
      if (isSolidTile(tx, ty)) tiles.push({ tx, ty });
    }
  }
  return tiles;
}

function moveAndCollide(p, dt) {
  // Horizontal
  p.x += p.vx * dt;
  for (const { tx, ty } of rectTiles(p.x, p.y, p.w, p.h)) {
    const tileLeft = tx * TILE, tileRight = tileLeft + TILE;
    if (p.vx > 0) p.x = tileLeft - p.w;
    else if (p.vx < 0) p.x = tileRight;
    p.vx = 0;
  }
  if (p.x < 0) { p.x = 0; p.vx = 0; }

  // Vertical
  p.y += p.vy * dt;
  p.onGround = false;
  for (const { tx, ty } of rectTiles(p.x, p.y, p.w, p.h)) {
    const tileTop = ty * TILE, tileBottom = tileTop + TILE;
    if (p.vy > 0) { p.y = tileTop - p.h; p.onGround = true; }
    else if (p.vy < 0) { p.y = tileBottom; }
    p.vy = 0;
  }
}

// ---------------------------------------------------------------
// Update
// ---------------------------------------------------------------
function killPlayer() {
  // No invulnerability gate here: falling/timeout must always kill instantly.
  // Enemy-contact damage is already gated by hurtPlayer()'s own invuln check
  // before it ever reaches this function.
  lives--;
  hud.lives.textContent = Math.max(lives, 0);
  if (lives <= 0) {
    state = 'gameover';
    showOverlay('GAME OVER', `Puntaje final: ${score}. Presioná R o el botón para reintentar.`, 'REINTENTAR');
    return;
  }
  currentPowerState = 'small';
  player = newPlayer(level.spawn, 'small');
  timeLeft = LEVEL_TIME;
  invulnUntil = Date.now() + INVULN_TIME;
}

function damageVillain() {
  const v = level.villain;
  if (!v || !v.alive || Date.now() < v.hitUntil) return;
  v.hp--;
  v.hitUntil = Date.now() + 500;
  if (v.hp <= 0) {
    v.alive = false;
    score += 5000;
  } else {
    score += 200;
  }
  hud.score.textContent = score;
}

function hurtPlayer() {
  if (Date.now() < invulnUntil) return;
  if (player.powerState !== 'small') {
    setPowerState(player.powerState === 'fire' ? 'big' : 'small');
    invulnUntil = Date.now() + INVULN_TIME;
    return;
  }
  killPlayer();
}

function completeLevel() {
  state = 'levelcomplete';
  stateTimer = 1400;
  score += Math.floor(timeLeft) * 5;
}

function showOverlay(title, msg, btnLabel) {
  overlayTitle.textContent = title;
  overlayMsg.textContent = msg;
  overlayBtn.textContent = btnLabel;
  overlay.classList.remove('hidden');
}

function updatePlaying(dt) {
  // horizontal input
  const accel = player.onGround ? MOVE_ACCEL : AIR_ACCEL;
  if (keys.left && !keys.right) {
    player.vx -= accel * dt;
    player.facing = -1;
  } else if (keys.right && !keys.left) {
    player.vx += accel * dt;
    player.facing = 1;
  } else if (player.onGround) {
    player.vx *= FRICTION;
    if (Math.abs(player.vx) < 0.05) player.vx = 0;
  }
  player.vx = Math.max(-MAX_SPEED, Math.min(MAX_SPEED, player.vx));

  // jump: buffered press + coyote time, so a tap always registers even if it
  // lands a frame or two before touching ground / after leaving a ledge
  const now = performance.now();
  if (player.onGround) coyoteUntil = now + COYOTE_MS;
  if (now < jumpBufferUntil && now < coyoteUntil) {
    player.vy = JUMP_VELOCITY;
    player.onGround = false;
    jumpBufferUntil = 0;
    coyoteUntil = 0;
  }
  if (!keys.jump && player.vy < JUMP_VELOCITY * JUMP_CUT) {
    player.vy = JUMP_VELOCITY * JUMP_CUT;
  }

  // shoot (fire flower only)
  if (now < shootBufferUntil && player.powerState === 'fire' && now - lastShotAt > SHOOT_COOLDOWN_MS) {
    spawnFireball();
    lastShotAt = now;
    shootBufferUntil = 0;
  }

  // gravity
  player.vy += GRAVITY * dt;
  if (player.vy > MAX_FALL) player.vy = MAX_FALL;

  moveAndCollide(player, dt);

  // fell into a pit
  if (player.y > level.pixelHeight + 60) {
    killPlayer();
    return;
  }

  // coins
  for (const c of level.coins) {
    if (c.taken) continue;
    const dx = (player.x + player.w / 2) - c.x;
    const dy = (player.y + player.h / 2) - c.y;
    if (Math.abs(dx) < 20 && Math.abs(dy) < 20) {
      c.taken = true;
      coinsCollected++;
      score += 100;
      hud.coins.textContent = coinsCollected;
      hud.score.textContent = score;
    }
  }

  // mushrooms (grow)
  for (const m of level.mushrooms) {
    if (m.taken) continue;
    if (aabbOverlap(player, m)) {
      m.taken = true;
      if (player.powerState === 'small') setPowerState('big');
      score += MUSHROOM_SCORE;
      hud.score.textContent = score;
    }
  }

  // flowers (fire power)
  for (const f of level.flowers) {
    if (f.taken) continue;
    if (aabbOverlap(player, f)) {
      f.taken = true;
      setPowerState('fire');
      score += FLOWER_SCORE;
      hud.score.textContent = score;
    }
  }

  updateFireballs(dt);

  // goombas
  for (const g of level.goombas) {
    if (!g.alive) continue;
    g.x += g.vx * dt;
    if (g.x < g.minX) { g.x = g.minX; g.vx = Math.abs(g.vx); }
    if (g.x + g.w > g.maxX) { g.x = g.maxX - g.w; g.vx = -Math.abs(g.vx); }

    const overlapX = player.x < g.x + g.w && player.x + player.w > g.x;
    const overlapY = player.y < g.y + g.h && player.y + player.h > g.y;
    if (overlapX && overlapY) {
      const stomped = player.vy > 0 && (player.y + player.h - g.y) < STOMP_TOLERANCE;
      if (stomped) {
        g.alive = false;
        player.vy = STOMP_BOUNCE;
        score += 100;
        hud.score.textContent = score;
      } else {
        hurtPlayer();
        return;
      }
    }
  }

  // villain (boss)
  if (level.villain && level.villain.alive) {
    const v = level.villain;
    v.x += v.vx * dt;
    if (v.x < v.minX) { v.x = v.minX; v.vx = Math.abs(v.vx); }
    if (v.x + v.w > v.maxX) { v.x = v.maxX - v.w; v.vx = -Math.abs(v.vx); }

    if (aabbOverlap(player, v)) {
      const stomped = player.vy > 0 && (player.y + player.h - v.y) < STOMP_TOLERANCE;
      if (stomped) {
        player.vy = STOMP_BOUNCE;
        damageVillain();
      } else {
        hurtPlayer();
        return;
      }
    }
  }

  // flag
  const dxf = (player.x + player.w / 2) - level.flag.x;
  if (Math.abs(dxf) < 18 && player.y + player.h > level.flag.topY) {
    completeLevel();
    return;
  }

  // timer
  timeAccum += dt / 60;
  if (timeAccum >= 1) {
    timeAccum = 0;
    timeLeft--;
    hud.time.textContent = Math.max(timeLeft, 0);
    if (timeLeft <= 0) { killPlayer(); return; }
  }

  // camera
  const target = player.x + player.w / 2 - CANVAS_W / 2;
  camera.x = Math.max(0, Math.min(target, Math.max(0, level.pixelWidth - CANVAS_W)));
}

function update(dt) {
  if (state === 'playing') {
    updatePlaying(dt);
  } else if (state === 'levelcomplete') {
    stateTimer -= dt * (1000 / 60);
    if (stateTimer <= 0) {
      if (levelIndex + 1 < LEVEL_SPECS.length) {
        loadLevel(levelIndex + 1);
        state = 'playing';
      } else {
        state = 'win';
        showOverlay('¡GANASTE!', `Completaste todos los niveles. Puntaje final: ${score} con ${coinsCollected} monedas.`, 'JUGAR DE NUEVO');
      }
    }
  }
}

// ---------------------------------------------------------------
// Render
// ---------------------------------------------------------------
function drawBackground() {
  const g = ctx.createLinearGradient(0, 0, 0, CANVAS_H);
  g.addColorStop(0, '#5c94fc');
  g.addColorStop(1, '#9fd0ff');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

  // parallax hills
  ctx.fillStyle = 'rgba(255,255,255,0.55)';
  const parallax = camera.x * 0.35;
  for (let i = -1; i < 8; i++) {
    const bx = i * 220 - (parallax % 220);
    ctx.beginPath();
    ctx.arc(bx, CANVAS_H - 40, 70, Math.PI, 0);
    ctx.fill();
  }
  ctx.fillStyle = 'rgba(255,255,255,0.75)';
  const parallax2 = camera.x * 0.6;
  for (let i = -1; i < 10; i++) {
    const cx = i * 160 - (parallax2 % 160) + 40;
    ctx.beginPath();
    ctx.arc(cx, 60, 18, 0, Math.PI * 2);
    ctx.arc(cx + 22, 55, 22, 0, Math.PI * 2);
    ctx.arc(cx + 46, 60, 16, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawTiles() {
  const tx0 = Math.floor(camera.x / TILE);
  const tx1 = Math.ceil((camera.x + CANVAS_W) / TILE);
  for (let ty = 0; ty < level.height; ty++) {
    for (let tx = Math.max(0, tx0); tx <= Math.min(level.width - 1, tx1); tx++) {
      if (!level.solid[ty][tx]) continue;
      const px = tx * TILE - camera.x, py = ty * TILE;
      const exposedTop = ty === 0 || !level.solid[ty - 1][tx];
      if (exposedTop) {
        ctx.fillStyle = '#5cc25c';
        ctx.fillRect(px, py, TILE, 8);
        ctx.fillStyle = '#8b5a2b';
        ctx.fillRect(px, py + 8, TILE, TILE - 8);
      } else {
        ctx.fillStyle = '#8b5a2b';
        ctx.fillRect(px, py, TILE, TILE);
      }
      ctx.strokeStyle = 'rgba(0,0,0,0.12)';
      ctx.strokeRect(px + 0.5, py + 0.5, TILE - 1, TILE - 1);
    }
  }
}

function drawCoins(t) {
  for (const c of level.coins) {
    if (c.taken) continue;
    const px = c.x - camera.x;
    if (px < -20 || px > CANVAS_W + 20) continue;
    const scale = 0.7 + 0.3 * Math.abs(Math.sin(t / 220 + c.x));
    ctx.save();
    ctx.translate(px, c.y);
    ctx.scale(scale, 1);
    ctx.beginPath();
    ctx.arc(0, 0, 9, 0, Math.PI * 2);
    ctx.fillStyle = '#ffd166';
    ctx.fill();
    ctx.strokeStyle = '#c9922c';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.restore();
  }
}

function drawGoombas() {
  for (const g of level.goombas) {
    if (!g.alive) continue;
    const px = g.x - camera.x;
    if (px < -40 || px > CANVAS_W + 40) continue;
    ctx.fillStyle = '#8b4a2b';
    ctx.beginPath();
    ctx.ellipse(px + g.w / 2, g.y + g.h / 2, g.w / 2, g.h / 2, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#5c2f16';
    ctx.fillRect(px + 2, g.y + g.h - 6, 8, 6);
    ctx.fillRect(px + g.w - 10, g.y + g.h - 6, 8, 6);
    ctx.fillStyle = '#fff';
    ctx.beginPath();
    ctx.arc(px + g.w / 2 - 5, g.y + g.h / 2 - 2, 4, 0, Math.PI * 2);
    ctx.arc(px + g.w / 2 + 5, g.y + g.h / 2 - 2, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.arc(px + g.w / 2 - 5, g.y + g.h / 2 - 2, 2, 0, Math.PI * 2);
    ctx.arc(px + g.w / 2 + 5, g.y + g.h / 2 - 2, 2, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawFlag() {
  const px = level.flag.x - camera.x;
  ctx.strokeStyle = '#c7c7c7';
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(px, level.flag.topY);
  ctx.lineTo(px, level.flag.y + TILE);
  ctx.stroke();
  ctx.fillStyle = '#29d985';
  ctx.beginPath();
  ctx.moveTo(px, level.flag.topY + 6);
  ctx.lineTo(px + 26, level.flag.topY + 16);
  ctx.lineTo(px, level.flag.topY + 26);
  ctx.closePath();
  ctx.fill();
}

function drawPlayer() {
  if (Date.now() < invulnUntil && Math.floor(Date.now() / 100) % 2 === 0) return;
  const px = player.x - camera.x;
  const w = player.w, h = player.h;
  const cowlH = 10, faceH = 8, shoesH = 6;
  const bodyTop = cowlH + faceH - 1;
  const suitH = h - bodyTop;
  const accent = player.powerState === 'fire' ? '#ff8a3d' : '#ffd166';

  ctx.save();
  ctx.translate(px + w / 2, player.y);
  ctx.scale(player.facing, 1);
  ctx.translate(-w / 2, 0);

  // cape trailing behind (opposite the facing direction)
  ctx.fillStyle = '#14161c';
  ctx.beginPath();
  ctx.moveTo(w * 0.3, cowlH - 2);
  ctx.lineTo(-w * 0.6, h * 0.55);
  ctx.lineTo(-w * 0.2, h);
  ctx.lineTo(w * 0.55, bodyTop + 2);
  ctx.closePath();
  ctx.fill();

  // cowl with pointed ears
  ctx.fillStyle = '#20242e';
  ctx.beginPath();
  ctx.moveTo(2, cowlH);
  ctx.lineTo(0, -6);
  ctx.lineTo(w * 0.3, cowlH * 0.4);
  ctx.lineTo(w * 0.7, cowlH * 0.4);
  ctx.lineTo(w, -6);
  ctx.lineTo(w - 2, cowlH);
  ctx.closePath();
  ctx.fill();
  ctx.fillRect(0, cowlH * 0.5, w, cowlH * 0.6);

  // jaw / face under the cowl
  ctx.fillStyle = '#e8b88a';
  ctx.fillRect(3, cowlH, w - 6, faceH);

  // white eye slits
  ctx.fillStyle = '#fff';
  ctx.fillRect(w * 0.55, cowlH + 2, 5, 2.5);
  ctx.fillRect(w * 0.2, cowlH + 2, 5, 2.5);

  // suit
  ctx.fillStyle = '#2b2f38';
  ctx.fillRect(0, bodyTop, w, suitH);

  // utility belt
  ctx.fillStyle = '#171920';
  ctx.fillRect(0, bodyTop + suitH * 0.45, w, 4);

  // chest emblem
  ctx.fillStyle = accent;
  ctx.beginPath();
  ctx.ellipse(w / 2, bodyTop + 6, w * 0.28, 5, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#0c0d10';
  ctx.beginPath();
  ctx.moveTo(w / 2 - 4, bodyTop + 6);
  ctx.lineTo(w / 2 - 1, bodyTop + 3.5);
  ctx.lineTo(w / 2, bodyTop + 6);
  ctx.lineTo(w / 2 + 1, bodyTop + 3.5);
  ctx.lineTo(w / 2 + 4, bodyTop + 6);
  ctx.lineTo(w / 2, bodyTop + 8.5);
  ctx.closePath();
  ctx.fill();

  // gloves
  ctx.fillStyle = '#171920';
  ctx.fillRect(-3, bodyTop + 1, 5, 8);
  ctx.fillRect(w - 2, bodyTop + 1, 5, 8);

  // boots
  ctx.fillStyle = '#0c0d10';
  ctx.fillRect(1, h - shoesH, 8, shoesH);
  ctx.fillRect(w - 9, h - shoesH, 8, shoesH);

  ctx.restore();
}

function drawVillain() {
  const v = level.villain;
  if (!v || !v.alive) return;
  const px = v.x - camera.x;
  if (px < -50 || px > CANVAS_W + 50) return;
  if (Date.now() < v.hitUntil && Math.floor(Date.now() / 80) % 2 === 0) return;

  ctx.fillStyle = '#3ddc5c';
  ctx.beginPath();
  ctx.moveTo(px - 4, v.y + 6); ctx.lineTo(px + 2, v.y - 6); ctx.lineTo(px + 6, v.y + 4);
  ctx.lineTo(px + v.w * 0.35, v.y - 10); ctx.lineTo(px + v.w * 0.5, v.y + 2);
  ctx.lineTo(px + v.w * 0.65, v.y - 10); ctx.lineTo(px + v.w - 6, v.y + 4);
  ctx.lineTo(px + v.w - 2, v.y - 6); ctx.lineTo(px + v.w + 4, v.y + 6);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = '#f4f0ea';
  ctx.fillRect(px + 4, v.y + 4, v.w - 8, 14);

  ctx.strokeStyle = '#c0244a';
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.moveTo(px + 6, v.y + 13);
  ctx.quadraticCurveTo(px + v.w / 2, v.y + 20, px + v.w - 6, v.y + 13);
  ctx.stroke();

  ctx.fillStyle = '#1a1a1a';
  ctx.fillRect(px + v.w * 0.28, v.y + 9, 3, 4);
  ctx.fillRect(px + v.w * 0.65, v.y + 9, 3, 4);

  ctx.fillStyle = '#5a2d8c';
  ctx.fillRect(px, v.y + 18, v.w, v.h - 24);

  ctx.fillStyle = '#f2a53d';
  ctx.beginPath();
  ctx.moveTo(px + v.w / 2, v.y + 18);
  ctx.lineTo(px + v.w / 2 - 6, v.y + 24);
  ctx.lineTo(px + v.w / 2 + 6, v.y + 24);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = '#1a1a1a';
  ctx.fillRect(px + 1, v.y + v.h - 6, 9, 6);
  ctx.fillRect(px + v.w - 10, v.y + v.h - 6, 9, 6);

  for (let i = 0; i < 3; i++) {
    ctx.fillStyle = i < v.hp ? '#ff5e5e' : 'rgba(255,255,255,0.25)';
    ctx.beginPath();
    ctx.arc(px + v.w / 2 - 12 + i * 12, v.y - 16, 4, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawMushrooms() {
  for (const m of level.mushrooms) {
    if (m.taken) continue;
    const px = m.x - camera.x;
    if (px < -30 || px > CANVAS_W + 30) continue;
    ctx.fillStyle = '#f2d9b8';
    ctx.fillRect(px + m.w * 0.3, m.y + m.h * 0.45, m.w * 0.4, m.h * 0.55);
    ctx.fillStyle = '#e0392b';
    ctx.beginPath();
    ctx.arc(px + m.w / 2, m.y + m.h * 0.45, m.w / 2, Math.PI, 0);
    ctx.fill();
    ctx.fillRect(px, m.y + m.h * 0.3, m.w, m.h * 0.2);
    ctx.fillStyle = '#fff';
    ctx.beginPath();
    ctx.arc(px + m.w * 0.3, m.y + m.h * 0.25, 3, 0, Math.PI * 2);
    ctx.arc(px + m.w * 0.7, m.y + m.h * 0.25, 3, 0, Math.PI * 2);
    ctx.arc(px + m.w * 0.5, m.y + m.h * 0.12, 2.5, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawFlowers(t) {
  for (const f of level.flowers) {
    if (f.taken) continue;
    const px = f.x - camera.x;
    if (px < -30 || px > CANVAS_W + 30) continue;
    const bob = Math.sin(t / 260 + f.x) * 1.5;
    const cx = px + f.w / 2, cy = f.y + f.h / 2 + bob;
    ctx.strokeStyle = '#29d985';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(cx, cy + 6);
    ctx.lineTo(cx, f.y + f.h);
    ctx.stroke();
    ctx.fillStyle = '#fff';
    for (let i = 0; i < 4; i++) {
      const ang = (Math.PI / 2) * i + Math.PI / 4;
      ctx.beginPath();
      ctx.arc(cx + Math.cos(ang) * 6, cy + Math.sin(ang) * 6, 5, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = '#ff8a3d';
    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawFireballs() {
  for (const fb of fireballs) {
    const px = fb.x - camera.x;
    ctx.fillStyle = '#ff7a1a';
    ctx.beginPath();
    ctx.arc(px, fb.y, fb.r, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#ffd166';
    ctx.beginPath();
    ctx.arc(px, fb.y, fb.r * 0.5, 0, Math.PI * 2);
    ctx.fill();
  }
}

function render(t) {
  drawBackground();
  drawTiles();
  drawCoins(t);
  drawMushrooms();
  drawFlowers(t);
  drawFireballs();
  drawGoombas();
  drawVillain();
  drawFlag();
  drawPlayer();

  if (state === 'levelcomplete') {
    ctx.fillStyle = 'rgba(0,0,0,0.35)';
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
    ctx.fillStyle = '#ffd166';
    ctx.font = 'bold 34px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`NIVEL ${level.name} COMPLETADO`, CANVAS_W / 2, CANVAS_H / 2);
  }
}

// ---------------------------------------------------------------
// Main loop
// ---------------------------------------------------------------
let lastTime = performance.now();
function loop(now) {
  let dt = (now - lastTime) / (1000 / 60);
  dt = Math.max(0.001, Math.min(dt, 2));
  lastTime = now;
  frameTime = now;

  if (state === 'playing' || state === 'levelcomplete') {
    update(dt);
    render(now);
  }
  requestAnimationFrame(loop);
}

showOverlay('BIT BROS', 'Un héroe murciélago corre y salta por la ciudad: pisá enemigos, agarrá el hongo para crecer y la flor para tirar fuego. Al final del último nivel te espera un villano con sonrisa siniestra.', 'JUGAR');
requestAnimationFrame(loop);
