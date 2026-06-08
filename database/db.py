"""
database/db.py
Conexión centralizada a SQLite y setup inicial de la base de datos.
Todas las funciones de acceso a datos pasan por este módulo.
"""

import sqlite3
import os
from pathlib import Path

# ── Rutas ────────────────────────────────────────────────────────────────────

BASE_DIR    = Path(__file__).resolve().parent.parent   # raíz del proyecto
DB_PATH     = BASE_DIR / "finanzas.db"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"


# ── Conexión ──────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """
    Devuelve una conexión a SQLite con:
    - Row factory para acceder a columnas por nombre (conn.row_factory)
    - Foreign keys activadas
    - WAL mode para mejor concurrencia
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # Permite row['columna'] en vez de row[0]
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# ── Setup inicial ─────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Inicializa la base de datos:
    1. Ejecuta schema.sql (crea tablas si no existen)
    2. Inserta datos por defecto (categorías, configuración)
    Seguro de llamar múltiples veces (usa INSERT OR IGNORE).
    """
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"No se encontró el schema en: {SCHEMA_PATH}")

    with get_connection() as conn:
        # 1. Crear tablas
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)

        # 2. Configuración por defecto
        _insertar_configuracion_default(conn)

        conn.commit()

    print(f"✅ Base de datos inicializada en: {DB_PATH}")


def _insertar_configuracion_default(conn: sqlite3.Connection) -> None:
    """Inserta valores de configuración iniciales si no existen."""
    defaults = [
        ("moneda_base",      "USD",       "Moneda principal de la app"),
        ("benchmark_ticker", "SPY",       "ETF usado como benchmark del portafolio"),
        ("perfil_riesgo",    "moderado",  "Perfil de riesgo del usuario"),
        ("nombre_usuario_1", "Usuario 1", "Nombre del primer usuario"),
        ("nombre_usuario_2", "Usuario 2", "Nombre del segundo usuario"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO configuracion (clave, valor, descripcion) VALUES (?, ?, ?)",
        defaults
    )


# ── Helpers genéricos ─────────────────────────────────────────────────────────

def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    """
    Ejecuta una consulta SELECT y devuelve lista de dicts.
    Uso: rows = fetch_all("SELECT * FROM gastos WHERE fecha = ?", ("2026-05-01",))
    """
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def fetch_one(query: str, params: tuple = ()) -> dict | None:
    """
    Ejecuta una consulta SELECT y devuelve un solo dict (o None si no hay resultado).
    """
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None


def execute_write(query: str, params: tuple = ()) -> int:
    """
    Ejecuta INSERT, UPDATE o DELETE.
    Devuelve el id del último registro insertado (lastrowid).
    """
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        conn.commit()
        return cursor.lastrowid


def execute_many(query: str, params_list: list[tuple]) -> int:
    """
    Ejecuta la misma query con múltiples filas de parámetros (bulk insert).
    Devuelve la cantidad de filas afectadas.
    """
    with get_connection() as conn:
        cursor = conn.executemany(query, params_list)
        conn.commit()
        return cursor.rowcount


# ── Helpers de configuración ──────────────────────────────────────────────────

def get_config(clave: str) -> str | None:
    """Devuelve el valor de una clave de configuración."""
    row = fetch_one("SELECT valor FROM configuracion WHERE clave = ?", (clave,))
    return row["valor"] if row else None


def set_config(clave: str, valor: str) -> None:
    """Actualiza o inserta un valor de configuración."""
    execute_write(
        """INSERT INTO configuracion (clave, valor)
           VALUES (?, ?)
           ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor,
                                            actualizado = datetime('now')""",
        (clave, valor)
    )


# ── Verificación rápida ───────────────────────────────────────────────────────

def verificar_db() -> dict:
    """
    Devuelve un resumen del estado de la base de datos.
    Útil para mostrar en el dashboard o para debugging.
    """
    tablas = [
        "activos", "operaciones", "posiciones", "lotes",
        "operaciones_cerradas", "gastos", "ingresos",
        "presupuestos", "cuentas", "deudas", "alertas"
    ]
    resumen = {}
    try:
        with get_connection() as conn:
            for tabla in tablas:
                cursor = conn.execute(f"SELECT COUNT(*) as n FROM {tabla}")
                resumen[tabla] = cursor.fetchone()["n"]
        resumen["estado"] = "ok"
        resumen["ruta_db"] = str(DB_PATH)
    except Exception as e:
        resumen["estado"] = "error"
        resumen["error"]  = str(e)
    return resumen


# ── Entry point para probar desde terminal ────────────────────────────────────

if __name__ == "__main__":
    init_db()
    estado = verificar_db()
    print("\n📊 Estado de la base de datos:")
    for k, v in estado.items():
        print(f"   {k}: {v}")
