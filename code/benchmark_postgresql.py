"""
=======================================================
  BENCHMARK COMPARATIVO DE HIPERVISORES
  Proxmox VM  (Tipo 1) → 192.168.137.7 / testing / nico
  VirtualBox  (Tipo 2) → 192.168.137.6 / electiva / luis
=======================================================
  Requisito: pip install psycopg2-binary
  Uso:       python benchmark_hipervisores.py
=======================================================
"""

import time
import csv
import statistics
import os
import psycopg2
from datetime import datetime

# ─────────────────────────────────────────────────────
#  CONFIGURACIÓN DE CONEXIONES
# ─────────────────────────────────────────────────────
DATABASES = {
    "Proxmox_Tipo1": {
        "host":     "192.168.137.7",
        "port":     5432,
        "dbname":   "testing",
        "user":     "nico",
        "password": "12345678",          # <-- ajusta si tiene contraseña
    },
    "VirtualBox_Tipo2": {
        "host":     "192.168.137.6",
        "port":     5432,
        "dbname":   "electiva",
        "user":     "luis",
        "password": "12345678",          # <-- ajusta si tiene contraseña
    },
}

# ─────────────────────────────────────────────────────
#  PARÁMETROS DEL BENCHMARK
# ─────────────────────────────────────────────────────
INSERT_ROWS      = 300_000   # filas para prueba de I/O
SORT_ROWS        = 500_000   # filas para prueba de CPU/sort
MATH_ROWS        = 500_000   # filas para prueba matemática
JOIN_ROWS        = 5_000     # filas por lado del join (reducido para evitar bloqueo)
REPETITIONS      = 3         # repeticiones por prueba (se promedia)

OUTPUT_CSV       = f"resultados_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# ─────────────────────────────────────────────────────
#  UTILIDADES
# ─────────────────────────────────────────────────────
def conectar(cfg: dict) -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        connect_timeout=10,
    )

def medir(conn, sql: str, params=None) -> float:
    """Ejecuta una consulta y devuelve el tiempo en segundos."""
    cur = conn.cursor()
    t0 = time.perf_counter()
    cur.execute(sql, params)
    conn.commit()
    elapsed = time.perf_counter() - t0
    cur.close()
    return round(elapsed, 4)

def promedio_repeticiones(conn, sql: str, reps: int) -> dict:
    tiempos = [medir(conn, sql) for _ in range(reps)]
    return {
        "min":    round(min(tiempos), 4),
        "max":    round(max(tiempos), 4),
        "avg":    round(statistics.mean(tiempos), 4),
        "stdev":  round(statistics.stdev(tiempos) if len(tiempos) > 1 else 0, 4),
    }

def separador(titulo: str):
    print(f"\n{'='*60}")
    print(f"  {titulo}")
    print('='*60)

def log(msg: str):
    print(f"  {msg}")

# ─────────────────────────────────────────────────────
#  PRUEBAS
# ─────────────────────────────────────────────────────

def prueba_io_escritura(conn) -> dict:
    """INSERT masivo (CHECKPOINT deshabilitado)."""
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS _bench_io")
    cur.execute("""
        CREATE UNLOGGED TABLE _bench_io (
            id     SERIAL PRIMARY KEY,
            valor  NUMERIC(12,6),
            codigo UUID,
            texto  TEXT
        )
    """)
    conn.commit()
    cur.close()

    sql = f"""
        INSERT INTO _bench_io (valor, codigo, texto)
        SELECT random()*999999,
               gen_random_uuid(),
               md5(random()::text) || md5(random()::text)
        FROM generate_series(1, {INSERT_ROWS})
    """
    t = medir(conn, sql)

    # CHECKPOINT eliminado para evitar error de permisos
    t_ck = 0.0

    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS _bench_io")
    conn.commit()
    cur.close()

    return {"insert_s": t, "checkpoint_s": t_ck, "total_s": round(t + t_ck, 4)}


def prueba_io_lectura(conn) -> dict:
    """Crea tabla, inserta datos, mide lectura secuencial e indexada."""
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS _bench_read")
    cur.execute(f"""
        CREATE UNLOGGED TABLE _bench_read AS
        SELECT (random()*999999)::NUMERIC(12,6) AS valor,
               md5(random()::text) AS texto
        FROM generate_series(1, {INSERT_ROWS})
    """)
    conn.commit()

    # Lectura secuencial
    t_seq = medir(conn, "SELECT COUNT(*), AVG(valor), MAX(valor) FROM _bench_read")

    # Crear índice
    t_idx_create = medir(conn, "CREATE INDEX idx_read_valor ON _bench_read(valor)")

    # 5 lecturas con índice (rango)
    rangos = [
        (0,      200000),
        (200000, 400000),
        (400000, 600000),
        (600000, 800000),
        (800000, 999999),
    ]
    tiempos_rango = []
    for lo, hi in rangos:
        t = medir(conn, f"SELECT COUNT(*) FROM _bench_read WHERE valor BETWEEN {lo} AND {hi}")
        tiempos_rango.append(t)

    cur.execute("DROP TABLE IF EXISTS _bench_read")
    conn.commit()
    cur.close()

    return {
        "seq_scan_s":    t_seq,
        "idx_create_s":  t_idx_create,
        "idx_reads_avg": round(statistics.mean(tiempos_rango), 4),
        "idx_reads_min": round(min(tiempos_rango), 4),
        "idx_reads_max": round(max(tiempos_rango), 4),
    }


def prueba_cpu_sort(conn) -> dict:
    """Ordenamiento intensivo en memoria."""
    sql = f"""
        SELECT COUNT(*) FROM (
            SELECT random() AS r
            FROM generate_series(1, {SORT_ROWS})
            ORDER BY r
        ) sub
    """
    return promedio_repeticiones(conn, sql, REPETITIONS)


def prueba_cpu_agregaciones(conn) -> dict:
    """Agregaciones estadísticas complejas."""
    sql = f"""
        SELECT COUNT(*),
               AVG(v), STDDEV(v),
               PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY v),
               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY v),
               PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY v)
        FROM (SELECT random()*100000 AS v
              FROM generate_series(1, {SORT_ROWS})) datos
    """
    return promedio_repeticiones(conn, sql, REPETITIONS)


def prueba_cpu_join(conn) -> dict:
    """Join analítico en memoria."""
    sql = f"""
        SELECT a.grupo, COUNT(*), AVG(a.valor), SUM(a.valor)
        FROM (SELECT (random()*100000)::INT AS valor,
                     (random()*10)::INT     AS grupo
              FROM generate_series(1, {JOIN_ROWS})) a
        JOIN (SELECT (random()*10)::INT     AS grupo,
                     (random()*100000)::INT AS umbral
              FROM generate_series(1, {JOIN_ROWS})) b
          ON a.grupo = b.grupo AND a.valor > b.umbral
        GROUP BY a.grupo ORDER BY SUM(a.valor) DESC
    """
    return promedio_repeticiones(conn, sql, REPETITIONS)


def prueba_cpu_math(conn) -> dict:
    """Funciones matemáticas FPU-intensivas."""
    sql = f"""
        SELECT COUNT(*), AVG(resultado)
        FROM (
            SELECT sqrt(abs(sin(n::float)*cos(n::float)*n))
                   + ln(n::float+1)
                   + power(mod(n,7)+1, 2.5) AS resultado
            FROM generate_series(1, {MATH_ROWS}) AS n
        ) calc
    """
    return promedio_repeticiones(conn, sql, REPETITIONS)


# ─────────────────────────────────────────────────────
#  RUNNER PRINCIPAL
# ─────────────────────────────────────────────────────

def ejecutar_benchmark(nombre: str, cfg: dict) -> dict:
    separador(f"EJECUTANDO: {nombre}  ({cfg['host']})")
    resultados = {"db": nombre, "host": cfg["host"]}

    try:
        conn = conectar(cfg)
        conn.autocommit = False

        # ── I/O ─────────────────────────────────────
        log("→ Prueba I/O: escritura masiva ...")
        r = prueba_io_escritura(conn)
        resultados["io_insert_s"]     = r["insert_s"]
        resultados["io_checkpoint_s"] = 0.0
        resultados["io_write_total_s"]= r["total_s"]
        log(f"   INSERT {INSERT_ROWS:,} filas: {r['insert_s']}s")

        log("→ Prueba I/O: lectura secuencial + índice ...")
        r = prueba_io_lectura(conn)
        resultados["io_seq_scan_s"]    = r["seq_scan_s"]
        resultados["io_idx_create_s"]  = r["idx_create_s"]
        resultados["io_idx_reads_avg"] = r["idx_reads_avg"]
        log(f"   Seq scan: {r['seq_scan_s']}s | Idx create: {r['idx_create_s']}s | Idx reads avg: {r['idx_reads_avg']}s")

        # ── CPU ─────────────────────────────────────
        log(f"→ Prueba CPU: sort {SORT_ROWS:,} filas ({REPETITIONS} reps) ...")
        r = prueba_cpu_sort(conn)
        resultados["cpu_sort_avg"]   = r["avg"]
        resultados["cpu_sort_min"]   = r["min"]
        resultados["cpu_sort_max"]   = r["max"]
        resultados["cpu_sort_stdev"] = r["stdev"]
        log(f"   avg={r['avg']}s  min={r['min']}s  max={r['max']}s")

        log(f"→ Prueba CPU: agregaciones ({REPETITIONS} reps) ...")
        r = prueba_cpu_agregaciones(conn)
        resultados["cpu_agg_avg"]   = r["avg"]
        resultados["cpu_agg_min"]   = r["min"]
        resultados["cpu_agg_max"]   = r["max"]
        resultados["cpu_agg_stdev"] = r["stdev"]
        log(f"   avg={r['avg']}s  min={r['min']}s  max={r['max']}s")

        log(f"→ Prueba CPU: join analítico ({REPETITIONS} reps) ...")
        r = prueba_cpu_join(conn)
        resultados["cpu_join_avg"]   = r["avg"]
        resultados["cpu_join_min"]   = r["min"]
        resultados["cpu_join_max"]   = r["max"]
        resultados["cpu_join_stdev"] = r["stdev"]
        log(f"   avg={r['avg']}s  min={r['min']}s  max={r['max']}s")

        log(f"→ Prueba CPU: funciones matemáticas ({REPETITIONS} reps) ...")
        r = prueba_cpu_math(conn)
        resultados["cpu_math_avg"]   = r["avg"]
        resultados["cpu_math_min"]   = r["min"]
        resultados["cpu_math_max"]   = r["max"]
        resultados["cpu_math_stdev"] = r["stdev"]
        log(f"   avg={r['avg']}s  min={r['min']}s  max={r['max']}s")

        conn.close()
        resultados["error"] = ""

    except Exception as e:
        log(f"  ❌ ERROR: {e}")
        resultados["error"] = str(e)

    return resultados


def generar_csv(datos: list, path: str):
    if not datos:
        return
    campos = list(datos[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(datos)
    print(f"\n  ✅ CSV guardado en: {os.path.abspath(path)}")


def imprimir_comparativa(resultados: list):
    if len(resultados) < 2:
        return
    a, b = resultados[0], resultados[1]

    separador("COMPARATIVA FINAL")
    fmt = "{:<30} {:>14} {:>14} {:>12}"
    print(fmt.format("Métrica", a["db"][:14], b["db"][:14], "Diferencia"))
    print("-" * 72)

    metricas = [
        ("IO — INSERT (s)",           "io_insert_s"),
        ("IO — CHECKPOINT (s)",       "io_checkpoint_s"),
        ("IO — Escritura total (s)",  "io_write_total_s"),
        ("IO — Seq scan (s)",         "io_seq_scan_s"),
        ("IO — Crear índice (s)",     "io_idx_create_s"),
        ("IO — Lecturas idx avg (s)", "io_idx_reads_avg"),
        ("CPU — Sort avg (s)",        "cpu_sort_avg"),
        ("CPU — Agregaciones avg (s)","cpu_agg_avg"),
        ("CPU — Join avg (s)",        "cpu_join_avg"),
        ("CPU — Math avg (s)",        "cpu_math_avg"),
    ]

    for label, key in metricas:
        va = a.get(key, "N/A")
        vb = b.get(key, "N/A")
        if isinstance(va, float) and isinstance(vb, float) and vb != 0:
            diff = f"{((va - vb) / vb * 100):+.1f}%"
        else:
            diff = "N/A"
        print(fmt.format(label, str(va), str(vb), diff))

    print("-" * 72)
    print(f"  (+%) = {a['db'][:14]} más lento | (-%) = {a['db'][:14]} más rápido")


# ─────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  BENCHMARK HIPERVISORES — PostgreSQL")
    print(f"  Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Repeticiones por prueba: {REPETITIONS}")
    print(f"  Filas I/O: {INSERT_ROWS:,}  |  CPU sort: {SORT_ROWS:,}")
    print("="*60)

    todos = []
    for nombre, cfg in DATABASES.items():
        r = ejecutar_benchmark(nombre, cfg)
        todos.append(r)

    imprimir_comparativa(todos)
    generar_csv(todos, OUTPUT_CSV)

    print(f"\n  Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")