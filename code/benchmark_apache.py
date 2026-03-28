"""
=======================================================
  BENCHMARK DE SERVIDOR WEB (Apache/Nginx)
  Proxmox VM  (Tipo 1) → http://192.168.137.7/
  VirtualBox  (Tipo 2) → http://192.168.137.6/
=======================================================
  Requisito: pip install requests
  Uso:       python benchmark_apache.py
=======================================================
"""

import requests
import time
import concurrent.futures
import statistics
import csv
from datetime import datetime

# ─────────────────────────────────────────────────────
#  CONFIGURACIÓN
# ─────────────────────────────────────────────────────
TARGETS = {
    "Proxmox_Tipo1": "http://192.168.137.7/",
    "VirtualBox_Tipo2": "http://192.168.137.6/"
}

# Ajusta estos valores según la capacidad de tu red y CPU
REQUESTS_COUNT = 2000  # Número total de peticiones por servidor
CONCURRENCY    = 50    # Número de hilos simultáneos (simula usuarios)

# ─────────────────────────────────────────────────────
#  FUNCIONES
# ─────────────────────────────────────────────────────
def benchmark_request(url):
    """Realiza una petición HTTP y mide la latencia."""
    start_time = time.perf_counter()
    try:
        # stream=True y content.read para descargar pero no guardar en RAM masiva
        response = requests.get(url, timeout=5, stream=True)
        # Forzamos leer el contenido para medir tiempo real de transferencia
        _ = response.content 
        end_time = time.perf_counter()
        return end_time - start_time, response.status_code
    except requests.RequestException:
        return None, None

def run_benchmark(name, url):
    print(f"\n-> Iniciando benchmark para: {name}")
    print(f"   URL: {url}")
    print(f"   Configuración: {REQUESTS_COUNT} peticiones total | {CONCURRENCY} hilos concurrentes.")
    
    times = []
    errors = 0
    status_codes = {}
    
    start_total = time.perf_counter()

    # Usamos ThreadPoolExecutor para concurrencia
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        # Lanzamos todas las peticiones
        futures = [executor.submit(benchmark_request, url) for _ in range(REQUESTS_COUNT)]
        
        # Procesamos a medida que terminan
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            if (i + 1) % (REQUESTS_COUNT // 5) == 0:
                print(f"   ... {(i + 1)} / {REQUESTS_COUNT} completados", end="\r")
                
            elapsed, code = future.result()
            
            if elapsed is not None:
                times.append(elapsed)
                # Contar códigos de estado
                status_codes[code] = status_codes.get(code, 0) + 1
                if code != 200:
                    errors += 1
            else:
                errors += 1

    end_total = time.perf_counter()
    total_time = end_total - start_total
    
    print(" " * 40, end="\r") # Limpiar línea de progreso
    
    valid_times = [t for t in times if t is not None]
    
    if not valid_times:
        print(f"[ERROR] Error crítico: No se puede conectar a {url}")
        return None

    # Cálculo de métricas
    rps = len(valid_times) / total_time
    avg_latency = statistics.mean(valid_times)
    min_latency = min(valid_times)
    max_latency = max(valid_times)
    stdev_latency = statistics.stdev(valid_times) if len(valid_times) > 1 else 0

    results = {
        "Target": name,
        "IP": url,
        "Total Requests": REQUESTS_COUNT,
        "Concurrency": CONCURRENCY,
        "Total Time (s)": round(total_time, 4),
        "RPS (Req/s)": round(rps, 2),
        "Avg Latency (s)": round(avg_latency, 4),
        "Min Latency (s)": round(min_latency, 4),
        "Max Latency (s)": round(max_latency, 4),
        "StdDev Latency": round(stdev_latency, 4),
        "Errors": errors,
        "Status Codes": str(status_codes)
    }
    
    print(f"[OK] Finalizado para {name}:")
    print(f"   RPS (Request/sec): {results['RPS (Req/s)']:>8}  (Mayor es mejor)")
    print(f"   Latencia Promedio: {results['Avg Latency (s)']:>8}s (Menor es mejor)")
    print(f"   Errores: {errors} | Códigos: {status_codes}")
    
    return results

def main():
    print("="*60)
    print("  BENCHMARK WEB (Requests Per Second)")
    print("  Emulando carga HTTP sobre Apache/Nginx")
    print("="*60)
    
    all_results = []
    
    for name, url in TARGETS.items():
        res = run_benchmark(name, url)
        if res:
            all_results.append(res)
            # Pequeña pausa para no saturar la red local de golpe entre tests
            time.sleep(2)

    # ── Exportar CSV ──
    if all_results:
        filename = f"apache_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        keys = all_results[0].keys()
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_results)
        print(f"\n[FILE] Resultados guardados en: {filename}")
        
    # ── Comparativa Final ──
    if len(all_results) >= 2:
        print("\n" + "="*60)
        print(" COMPARATIVA DE RENDIMIENTO WEB (RPS)")
        print(" (Más solicitudes por segundo = Mejor servidor)")
        print("="*60)
        
        # Ordenar por RPS descendente
        sorted_res = sorted(all_results, key=lambda x: x['RPS (Req/s)'], reverse=True)
        
        winner = sorted_res[0]
        loser = sorted_res[-1]
        
        print(f" [1] GANADOR: {winner['Target']} confiabilidad {100 - (winner['Errors']/REQUESTS_COUNT*100):.1f}%")
        print(f"    RPS: {winner['RPS (Req/s)']}")
        print(f"    Latencia: {winner['Avg Latency (s)']}s")
        print("-" * 60)
        print(f" [2] SEGUNDO: {loser['Target']}")
        print(f"    RPS: {loser['RPS (Req/s)']}")
        print("-" * 60)

        if loser['RPS (Req/s)'] > 0:
            diff_percent = ((winner['RPS (Req/s)'] - loser['RPS (Req/s)']) / loser['RPS (Req/s)']) * 100
            print(f" -> {winner['Target']} es un {diff_percent:.2f}% más rápido que {loser['Target']}.")

if __name__ == "__main__":
    main()
