# Proyecto — IaaS y virtualización

Trabajo académico de la **Electiva IaaS y Virtualización** (Ingeniería de Sistemas y Computación, UPTC, Tunja, 2026). El proyecto implementa una red de tres máquinas virtuales con **Proxmox VE** (hipervisor Tipo 1) y **Oracle VirtualBox** (Tipo 2), servicios **Apache** y **PostgreSQL**, y pruebas comparativas de rendimiento.

**Integrantes:** Gabriel Fernando Castillo Mendieta, Esteban Nicolás Peña Coronado, Luis Javier López Galindo, Johan Sebastián Gil Salamanca, Brayan Alejandro Cifuentes Quiroga.  
**Docente:** Frey Alfonso Santamaría Buitrago.

---

## Documentos principales

| Archivo | Descripción |
|---------|-------------|
| [**informe-investigacion.md**](informe-investigacion.md) | **Informe de investigación.** Marco teórico sobre virtualización, hipervisores Tipo 1 y 2, Proxmox VE (KVM, QEMU, VirtIO), VirtualBox, modos de red, benchmarking, Apache y PostgreSQL en entornos virtualizados, seguridad, análisis y respuestas por niveles (conceptual, técnico, comparativo, estratégico y reflexivo), incluyendo el caso ACME. |
| [**informe-tecnico.md**](informe-tecnico.md) | **Informe técnico de implementación.** Documentación paso a paso: instalación de Proxmox, creación de la MV en Proxmox, MV en VirtualBox (incluye Netplan), Fedora Workstation como cliente, IPs y credenciales, instalación de servicios, figuras del laboratorio y resultados de los benchmarks (Apache y PostgreSQL), análisis y conclusiones (incluye el contexto de hardware distinto entre equipos). |

Ambos archivos están en Markdown; pueden visualizarse en GitHub, en el editor o exportarse a PDF con herramientas como Pandoc.

---

## Material relacionado (opcional)

- **`code/`** — Scripts de pruebas: `benchmak_apache.py` y `benchmark_postgresql.py`.
- **`files/`** — Resultados en CSV de las ejecuciones de benchmark.
- **`images/`** — Capturas referenciadas desde `informe-tecnico.md`.

---

## Cómo leer el repositorio

1. Empezar por **informe-investigacion.md** si buscas fundamentos, comparación de arquitecturas y criterios de decisión.
2. Usar **informe-tecnico.md** para reproducir la infraestructura, revisar la topología de red y los resultados medidos en laboratorio.
