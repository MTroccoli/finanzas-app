/* ============================================================
   BIT BROS — platformer clásico en Canvas 2D, sin dependencias.
   ============================================================ */

const TILE = 32;
const CANVAS_W = 800;
const CANVAS_H = 480;

const GRAVITY = 0.62;
const MAX_FALL = 15;
const MOVE_ACCEL = 0.7;
const MAX_SPEED = 4.4;
const AIR_ACCEL = 0.5;
const FRICTION = 0.78;
const JUMP_VELOCITY = -11.8;
const JUMP_CUT = 0.5;
const STOMP_BOUNCE = -8.5;
const STOMP_TOLERANCE = 14;
const INVULN_TIME = 1500;
const LEVEL_TIME = 400;

// ---------------------------------------------------------------
// Level builder: programmatic spec -> tile grid + entity lists
// ---------------------------------------------------------------
function buildLevel(spec) {
  const { width, height, groundY, pits = [], platforms = [], coins = [],
          goombas = [], flag, spawn, name } = spec;

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
    platforms: [
      { x: 8, y: 9, w: 4 },
      { x: 22, y: 10, w: 3 },
      { x: 30, y: 8, w: 5 },
      { x: 44, y: 9, w: 4 },
      { x: 52, y: 11, w: 3 },
      { x: 60, y: 8, w: 4 },
    ],
    coins: [
      [9, 8], [10, 8], [11, 8],
      [23, 9], [24, 9],
      [31, 7], [32, 7], [33, 7], [34, 7],
      [45, 8], [46, 8],
      [61, 7], [62, 7], [63, 7],
      [5, 12], [14, 12], [26, 12], [36, 12], [50, 12],
    ],
    goombas: [
      { x: 12, y: 13, range: [10, 17] },
      { x: 25, y: 13, range: [23, 39] },
      { x: 46, y: 13, range: [43, 51] },
      { x: 58, y: 13, range: [55, 66] },
    ],
    flag: { x: 66, y: 3 },
    spawn: { x: 2, y: 11 },
  },
  {
    name: '1-2',
    width: 85, height: 15, groundY: 13,
    pits: [[10, 11], [24, 26], [38, 39], [55, 58], [70, 71]],
    platforms: [
      { x: 5, y: 9, w: 3 },
      { x: 14, y: 10, w: 4 },
      { x: 20, y: 7, w: 3 },
      { x: 29, y: 9, w: 5 },
      { x: 42, y: 8, w: 3 },
      { x: 47, y: 10, w: 4 },
      { x: 60, y: 9, w: 4 },
      { x: 66, y: 7, w: 3 },
      { x: 75, y: 9, w: 5 },
    ],
    coins: [
      [6, 8], [15, 9], [16, 9], [21, 6], [30, 8], [31, 8], [32, 8],
      [43, 7], [48, 9], [49, 9], [61, 8], [62, 8], [67, 6],
      [76, 8], [77, 8], [78, 8], [79, 8],
      [2, 12], [18, 12], [34, 12], [45, 12], [63, 12],
    ],
    goombas: [
      { x: 8, y: 13, range: [4, 9] },
      { x: 16, y: 10, range: [14, 17] },
      { x: 30, y: 9, range: [29, 33] },
      { x: 44, y: 13, range: [41, 54] },
      { x: 61, y: 13, range: [59, 69] },
      { x: 76, y: 9, range: [75, 79] },
      { x: 80, y: 13, range: [73, 84] },
    ],
    flag: { x: 82, y: 3 },
    spawn: { x: 2, y: 11 },
  },
  {
    name: '1-3',
    width: 100, height: 15, groundY: 13,
    pits: [[9, 10], [20, 22], [33, 34], [44, 47], [58, 60], [72, 74], [88, 90]],
    platforms: [
      { x: 4, y: 9, w: 3 }, { x: 12, y: 7, w: 3 }, { x: 17, y: 10, w: 3 },
      { x: 24, y: 8, w: 4 }, { x: 30, y: 6, w: 3 }, { x: 36, y: 9, w: 5 },
      { x: 48, y: 8, w: 3 }, { x: 52, y: 6, w: 3 }, { x: 62, y: 9, w: 4 },
      { x: 68, y: 7, w: 3 }, { x: 76, y: 10, w: 4 }, { x: 82, y: 8, w: 3 },
      { x: 92, y: 9, w: 6 },
    ],
    coins: [
      [5, 8], [13, 6], [18, 9], [25, 7], [26, 7], [31, 5], [37, 8], [38, 8], [39, 8],
      [49, 7], [53, 5], [63, 8], [64, 8], [69, 6], [77, 9], [78, 9], [83, 7],
      [93, 8], [94, 8], [95, 8], [96, 8],
      [2, 12], [15, 12], [28, 12], [42, 12], [55, 12], [65, 12], [80, 12],
    ],
    goombas: [
      { x: 6, y: 13, range: [2, 8] },
      { x: 13, y: 7, range: [12, 14] },
      { x: 25, y: 13, range: [23, 32] },
      { x: 37, y: 9, range: [36, 40] },
      { x: 42, y: 13, range: [35, 43] },
      { x: 50, y: 13, range: [48, 57] },
      { x: 63, y: 9, range: [62, 65] },
      { x: 70, y: 13, range: [61, 71] },
      { x: 79, y: 13, range: [75, 87] },
      { x: 93, y: 9, range: [92, 97] },
      { x: 96, y: 13, range: [91, 99] },
    ],
    flag: { x: 97, y: 3 },
    spawn: { x: 2, y: 11 },
  },
];

// ---------------------------------------------------------------
// Input
// ---------------------------------------------------------------
const keys = { left: false, right: false, jump: false, jumpJustPressed: false };
let jumpHeldPrev = false;

window.addEventListener('keydown', e => {
  if (['ArrowLeft', 'KeyA'].includes(e.code)) keys.left = true;
  if (['ArrowRight', 'KeyD'].includes(e.code)) keys.right = true;
  if (['ArrowUp', 'KeyW', 'Space'].includes(e.code)) keys.jump = true;
  if (e.code === 'KeyR') restartGame();
  if (['Space', 'ArrowUp'].includes(e.code)) e.preventDefault();
});
window.addEventListener('keyup', e => {
  if (['ArrowLeft', 'KeyA'].includes(e.code)) keys.left = false;
  if (['ArrowRight', 'KeyD'].includes(e.code)) keys.right = false;
  if (['ArrowUp', 'KeyW', 'Space'].includes(e.code)) keys.jump = false;
});

function bindTouch(id, onDown, onUp) {
  const el = document.getElementById(id);
  const start = e => { e.preventDefault(); onDown(); };
  const end = e => { e.preventDefault(); onUp(); };
  el.addEventListener('touchstart', start, { passive: false });
  el.addEventListener('touchend', end, { passive: false });
  el.addEventListener('touchcancel', end, { passive: false });
  el.addEventListener('mousedown', start);
  el.addEventListener('mouseup', end);
  el.addEventListener('mouseleave', end);
}
bindTouch('btn-left', () => keys.left = true, () => keys.left = false);
bindTouch('btn-right', () => keys.right = true, () => keys.right = false);
bindTouch('btn-jump', () => keys.jump = true, () => keys.jump = false);

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

function newPlayer(spawn) {
  return {
    x: spawn.x, y: spawn.y, w: 22, h: 30,
    vx: 0, vy: 0, onGround: false, facing: 1, dead: false,
  };
}

function loadLevel(idx) {
  levelIndex = idx;
  level = buildLevel(LEVEL_SPECS[idx]);
  player = newPlayer(level.spawn);
  camera.x = 0;
  timeLeft = LEVEL_TIME;
  timeAccum = 0;
  hud.level.textContent = level.name;
}

function startGame() {
  score = 0; coinsCollected = 0; lives = 3;
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
  if (Date.now() < invulnUntil) return;
  lives--;
  hud.lives.textContent = Math.max(lives, 0);
  if (lives <= 0) {
    state = 'gameover';
    showOverlay('GAME OVER', `Puntaje final: ${score}. Presioná R o el botón para reintentar.`, 'REINTENTAR');
    return;
  }
  player = newPlayer(level.spawn);
  timeLeft = LEVEL_TIME;
  invulnUntil = Date.now() + INVULN_TIME;
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

  // jump
  const jumpJustPressed = keys.jump && !jumpHeldPrev;
  if (jumpJustPressed && player.onGround) {
    player.vy = JUMP_VELOCITY;
    player.onGround = false;
  }
  if (!keys.jump && player.vy < JUMP_VELOCITY * JUMP_CUT) {
    player.vy = JUMP_VELOCITY * JUMP_CUT;
  }
  jumpHeldPrev = keys.jump;

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
        killPlayer();
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
  ctx.save();
  ctx.translate(px + player.w / 2, player.y);
  ctx.scale(player.facing, 1);
  ctx.translate(-player.w / 2, 0);

  ctx.fillStyle = '#e0392b';
  ctx.fillRect(0, 0, player.w, 8);
  ctx.fillRect(-2, 6, player.w + 4, 5);

  ctx.fillStyle = '#f6c39a';
  ctx.fillRect(2, 8, player.w - 4, 10);

  ctx.fillStyle = '#2e5fd9';
  ctx.fillRect(0, 17, player.w, 13);

  ctx.fillStyle = '#f6c39a';
  ctx.fillRect(-3, 18, 5, 8);
  ctx.fillRect(player.w - 2, 18, 5, 8);

  ctx.fillStyle = '#3a2a1a';
  ctx.fillRect(1, player.h - 6, 8, 6);
  ctx.fillRect(player.w - 9, player.h - 6, 8, 6);

  ctx.fillStyle = '#000';
  ctx.fillRect(player.w - 8, 10, 3, 3);

  ctx.restore();
}

function render(t) {
  drawBackground();
  drawTiles();
  drawCoins(t);
  drawGoombas();
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

showOverlay('BIT BROS', 'Un platformer estilo retro. Corré, saltá, pisá enemigos y llegá a la bandera.', 'JUGAR');
requestAnimationFrame(loop);
