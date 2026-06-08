-- ============================================================
-- finanzas_app — schema.sql
-- Motor: SQLite 3
-- Convenciones:
--   * Fechas: TEXT en formato ISO 8601 (YYYY-MM-DD)
--   * Moneda: REAL en USD salvo indicación contraria
--   * Timestamps: TEXT en formato ISO 8601 con hora (YYYY-MM-DD HH:MM:SS)
--   * Soft-delete: columna activo INTEGER DEFAULT 1 donde aplique
-- ============================================================

PRAGMA journal_mode = WAL;   -- Mejor concurrencia en lecturas simultáneas
PRAGMA foreign_keys = ON;    -- Integridad referencial activada


-- ============================================================
-- 0. CONFIGURACIÓN DE LA APP
-- ============================================================

CREATE TABLE IF NOT EXISTS configuracion (
    clave       TEXT PRIMARY KEY,
    valor       TEXT NOT NULL,
    descripcion TEXT,
    actualizado TEXT DEFAULT (datetime('now'))
);

-- Valores iniciales sugeridos (se insertan desde db.py al hacer setup)
-- clave: 'moneda_base'       → 'USD'
-- clave: 'benchmark_ticker'  → 'SPY'
-- clave: 'perfil_riesgo'     → 'moderado'
-- clave: 'nombre_usuario_1'  → ''
-- clave: 'nombre_usuario_2'  → ''


-- ============================================================
-- 1. MÓDULO DE INVERSIONES
-- ============================================================

-- ------------------------------------------------------------
-- 1.1 Activos conocidos (catálogo local para autocompletar)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activos (
    ticker      TEXT PRIMARY KEY,
    nombre      TEXT,
    tipo        TEXT CHECK(tipo IN ('accion', 'etf', 'fondo', 'otro')),
    sector      TEXT,
    industria   TEXT,
    pais        TEXT,
    moneda      TEXT DEFAULT 'USD',
    activo      INTEGER DEFAULT 1,
    actualizado TEXT DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- 1.2 Operaciones de compra/venta
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operaciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL REFERENCES activos(ticker),
    tipo            TEXT NOT NULL CHECK(tipo IN ('compra', 'venta')),
    fecha           TEXT NOT NULL,                  -- YYYY-MM-DD
    cantidad        REAL NOT NULL CHECK(cantidad > 0),
    precio_unitario REAL NOT NULL CHECK(precio_unitario > 0),
    comision        REAL DEFAULT 0,
    monto_total     REAL GENERATED ALWAYS AS
                        (cantidad * precio_unitario + comision) VIRTUAL,
    fuente          TEXT DEFAULT 'manual'
                        CHECK(fuente IN ('manual', 'ibkr_csv', 'ibkr_xml')),
    ibkr_trade_id   TEXT UNIQUE,                    -- Para evitar duplicados al importar
    notas           TEXT,
    creado          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_operaciones_ticker ON operaciones(ticker);
CREATE INDEX IF NOT EXISTS idx_operaciones_fecha  ON operaciones(fecha);

-- ------------------------------------------------------------
-- 1.3 Posiciones abiertas (vista materializada / tabla auxiliar)
--     Se recalcula automáticamente desde operaciones.
--     Sirve como caché para no recalcular FIFO en cada carga.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posiciones (
    ticker              TEXT PRIMARY KEY REFERENCES activos(ticker),
    cantidad_total      REAL NOT NULL DEFAULT 0,
    costo_base_total    REAL NOT NULL DEFAULT 0,    -- Suma de (cantidad * precio) por lote
    precio_promedio     REAL GENERATED ALWAYS AS
                            (CASE WHEN cantidad_total > 0
                             THEN costo_base_total / cantidad_total
                             ELSE 0 END) VIRTUAL,
    primera_compra      TEXT,                       -- Fecha más antigua (para CAGR)
    actualizado         TEXT DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- 1.4 Lotes de compra (método FIFO para calcular costo al vender)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lotes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    operacion_id        INTEGER NOT NULL REFERENCES operaciones(id),
    ticker              TEXT NOT NULL REFERENCES activos(ticker),
    fecha_compra        TEXT NOT NULL,
    cantidad_original   REAL NOT NULL,
    cantidad_restante   REAL NOT NULL,              -- Decrece con cada venta
    precio_compra       REAL NOT NULL,
    comision_proporcional REAL DEFAULT 0,
    cerrado             INTEGER DEFAULT 0           -- 1 cuando cantidad_restante = 0
);

CREATE INDEX IF NOT EXISTS idx_lotes_ticker  ON lotes(ticker);
CREATE INDEX IF NOT EXISTS idx_lotes_cerrado ON lotes(cerrado);

-- ------------------------------------------------------------
-- 1.5 Operaciones cerradas (P&L realizado)
--     Una fila por cada "match" venta ↔ lote de compra (FIFO)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operaciones_cerradas (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker              TEXT NOT NULL REFERENCES activos(ticker),
    lote_id             INTEGER REFERENCES lotes(id),
    operacion_venta_id  INTEGER REFERENCES operaciones(id),
    fecha_compra        TEXT NOT NULL,
    fecha_venta         TEXT NOT NULL,
    cantidad            REAL NOT NULL,
    precio_compra       REAL NOT NULL,
    precio_venta        REAL NOT NULL,
    comision_compra     REAL DEFAULT 0,
    comision_venta      REAL DEFAULT 0,
    ganancia_perdida    REAL GENERATED ALWAYS AS
                            (cantidad * (precio_venta - precio_compra)
                             - comision_compra - comision_venta) VIRTUAL,
    dias_en_cartera     INTEGER GENERATED ALWAYS AS
                            (CAST(julianday(fecha_venta) - julianday(fecha_compra) AS INTEGER)) VIRTUAL,
    creado              TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_op_cerradas_ticker ON operaciones_cerradas(ticker);

-- ------------------------------------------------------------
-- 1.6 Precios históricos (caché local para no repetir llamadas a yfinance)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS precios_historicos (
    ticker  TEXT NOT NULL REFERENCES activos(ticker),
    fecha   TEXT NOT NULL,          -- YYYY-MM-DD
    apertura    REAL,
    maximo      REAL,
    minimo      REAL,
    cierre      REAL,
    cierre_ajustado REAL,
    volumen     INTEGER,
    PRIMARY KEY (ticker, fecha)
);

-- ------------------------------------------------------------
-- 1.7 Snapshot diario del portafolio (para gráfico de evolución)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS snapshots_portafolio (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha           TEXT NOT NULL,
    valor_mercado   REAL NOT NULL,      -- Suma de posiciones a precio de cierre
    costo_base      REAL NOT NULL,      -- Suma de costos de compra
    ganancia_no_realizada REAL GENERATED ALWAYS AS
                        (valor_mercado - costo_base) VIRTUAL,
    creado          TEXT DEFAULT (datetime('now')),
    UNIQUE(fecha)
);


-- ============================================================
-- 2. MÓDULO DE GASTOS
-- ============================================================

-- ------------------------------------------------------------
-- 2.1 Categorías de gastos
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categorias_gastos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    icono       TEXT,       -- Emoji o nombre de ícono para UI
    activo      INTEGER DEFAULT 1
);

-- Categorías predefinidas (se insertan desde db.py)
INSERT OR IGNORE INTO categorias_gastos (nombre, icono) VALUES
    ('Alimentación',    '🛒'),
    ('Transporte',      '🚗'),
    ('Salud',           '🏥'),
    ('Entretenimiento', '🎬'),
    ('Servicios',       '💡'),
    ('Educación',       '📚'),
    ('Vivienda',        '🏠'),
    ('Ropa',            '👕'),
    ('Viajes',          '✈️'),
    ('Inversiones',     '📈'),
    ('Otros',           '📦');

-- ------------------------------------------------------------
-- 2.2 Gastos
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gastos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha           TEXT NOT NULL,              -- YYYY-MM-DD
    monto           REAL NOT NULL CHECK(monto > 0),
    comercio        TEXT,                       -- Nombre del comercio/descripción
    categoria_id    INTEGER REFERENCES categorias_gastos(id),
    usuario         TEXT DEFAULT 'compartido'   -- 'usuario1', 'usuario2', 'compartido'
                        CHECK(usuario IN ('usuario1', 'usuario2', 'compartido')),
    fuente          TEXT DEFAULT 'manual'
                        CHECK(fuente IN ('manual', 'pdf', 'email')),
    referencia_ext  TEXT,                       -- ID o hash para evitar duplicados al importar
    notas           TEXT,
    creado          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gastos_fecha        ON gastos(fecha);
CREATE INDEX IF NOT EXISTS idx_gastos_categoria_id ON gastos(categoria_id);

-- ------------------------------------------------------------
-- 2.3 Importaciones de PDF / email (log de archivos procesados)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS importaciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        TEXT NOT NULL CHECK(tipo IN ('pdf', 'email', 'ibkr_csv', 'ibkr_xml')),
    nombre_archivo TEXT,
    hash_archivo   TEXT UNIQUE,    -- SHA256 para evitar reprocesar el mismo archivo
    registros_importados INTEGER DEFAULT 0,
    errores          INTEGER DEFAULT 0,
    creado           TEXT DEFAULT (datetime('now'))
);


-- ============================================================
-- 3. MÓDULO DE INGRESOS
-- ============================================================

-- ------------------------------------------------------------
-- 3.1 Tipos de ingreso
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tipos_ingreso (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT NOT NULL UNIQUE,
    activo  INTEGER DEFAULT 1
);

INSERT OR IGNORE INTO tipos_ingreso (nombre) VALUES
    ('Salario'),
    ('Freelance'),
    ('Dividendos'),
    ('Renta'),
    ('Reembolso'),
    ('Otros');

-- ------------------------------------------------------------
-- 3.2 Ingresos
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingresos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha       TEXT NOT NULL,              -- YYYY-MM-DD
    monto       REAL NOT NULL CHECK(monto > 0),
    descripcion TEXT,
    tipo_id     INTEGER REFERENCES tipos_ingreso(id),
    usuario     TEXT DEFAULT 'compartido'
                    CHECK(usuario IN ('usuario1', 'usuario2', 'compartido')),
    recurrente  INTEGER DEFAULT 0,          -- 1 = ingreso fijo mensual
    notas       TEXT,
    creado      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ingresos_fecha ON ingresos(fecha);


-- ============================================================
-- 4. MÓDULO DE PRESUPUESTO
-- ============================================================

-- ------------------------------------------------------------
-- 4.1 Límites mensuales por categoría
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS presupuestos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria_id    INTEGER NOT NULL REFERENCES categorias_gastos(id),
    anio            INTEGER NOT NULL,
    mes             INTEGER NOT NULL CHECK(mes BETWEEN 1 AND 12),
    limite_mensual  REAL NOT NULL CHECK(limite_mensual > 0),
    creado          TEXT DEFAULT (datetime('now')),
    UNIQUE(categoria_id, anio, mes)
);

-- ------------------------------------------------------------
-- 4.2 Metas de ahorro
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metas_ahorro (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    monto_objetivo  REAL NOT NULL CHECK(monto_objetivo > 0),
    monto_actual    REAL DEFAULT 0,
    fecha_inicio    TEXT NOT NULL,
    fecha_objetivo  TEXT,
    completada      INTEGER DEFAULT 0,
    notas           TEXT,
    creado          TEXT DEFAULT (datetime('now'))
);


-- ============================================================
-- 5. DASHBOARD — Patrimonio neto
-- ============================================================

-- ------------------------------------------------------------
-- 5.1 Cuentas (cash y otros activos no bursátiles)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cuentas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    tipo        TEXT NOT NULL CHECK(tipo IN ('cash', 'banco', 'ibkr_cash', 'otro')),
    moneda      TEXT DEFAULT 'USD',
    saldo       REAL DEFAULT 0,
    activo      INTEGER DEFAULT 1,
    actualizado TEXT DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- 5.2 Deudas / pasivos
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS deudas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    tipo            TEXT CHECK(tipo IN ('tarjeta', 'prestamo', 'hipoteca', 'otro')),
    saldo_pendiente REAL NOT NULL DEFAULT 0,
    tasa_interes    REAL DEFAULT 0,     -- % anual
    fecha_vencimiento TEXT,
    activo          INTEGER DEFAULT 1,
    actualizado     TEXT DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- 5.3 Snapshots de patrimonio neto (para gráfico de evolución)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS snapshots_patrimonio (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha               TEXT NOT NULL UNIQUE,
    valor_portafolio    REAL DEFAULT 0,
    cash_total          REAL DEFAULT 0,
    otros_activos       REAL DEFAULT 0,
    deudas_total        REAL DEFAULT 0,
    patrimonio_neto     REAL GENERATED ALWAYS AS
                            (valor_portafolio + cash_total + otros_activos - deudas_total) VIRTUAL,
    creado              TEXT DEFAULT (datetime('now'))
);


-- ============================================================
-- 6. ALERTAS
-- ============================================================

CREATE TABLE IF NOT EXISTS alertas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        TEXT NOT NULL CHECK(tipo IN (
                    'gasto_excesivo',
                    'caida_activo',
                    'meta_cumplida',
                    'rebalanceo',
                    'personalizada'
                )),
    mensaje     TEXT NOT NULL,
    leida       INTEGER DEFAULT 0,
    creado      TEXT DEFAULT (datetime('now'))
);
