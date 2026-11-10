import argparse
import csv
import json
import os
import platform
import random
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.parallel_futures import count_words_parallel
from src.sequential import count_words_sequential


SAMPLE_SENTENCES_MX = [
    "En México la diversidad cultural y lingüística enriquece cada región del país desde Baja California hasta Yucatán.",
    "La Ciudad de México, Guadalajara, Monterrey y Querétaro impulsan el desarrollo tecnológico y de ciencia de datos.",
    "El procesamiento de lenguaje natural y el cómputo de alto rendimiento permiten analizar millones de textos mexicanos.",
    "La gastronomía mexicana, reconocida como patrimonio cultural de la humanidad, incluye tacos, mole, pozole y tamales.",
    "Las universidades e institutos de investigación en México forman ingenieros en inteligencia artificial y datos.",
    "El modelo de programación MapReduce divide grandes volúmenes de información para procesarlos en paralelo.",
    "Durante las festividades del Día de Muertos se colocan ofrendas con cempasúchil, pan de muerto y calaveritas.",
    "La transición energética, la movilidad sustentable y la gestión del agua son retos prioritarios para el desarrollo nacional.",
    "El análisis estadístico de frecuencias de palabras revela patrones semánticos en noticias, redes sociales y literatura.",
    "Al distribuir el trabajo entre múltiples núcleos del procesador se reduce significativamente el tiempo de respuesta.",
    "La Sierra Madre Oriental y la Sierra Madre Occidental atraviesan el territorio mexicano creando ecosistemas únicos.",
    "En la ingeniería de datos moderna se utilizan flujos de lectura por streaming para optimizar el uso de memoria RAM.",
]


def generate_synthetic_mx_zip(
    zip_path: Path,
    num_files: int = 16,
    records_per_file: int = 5000,
    sentences_per_record: int = 6,
    seed: int = 42,
) -> None:
    """
    Genera un archivo ZIP con múltiples archivos JSON (`mx_01.json`, ...),
    cada uno con una lista de registros `{"id": ..., "text": ...}` con textos de México.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    record_id = 1
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for file_idx in range(1, num_files + 1):
            records = []
            for _ in range(records_per_file):
                chosen = rng.choices(SAMPLE_SENTENCES_MX, k=sentences_per_record)
                text = f"{' '.join(chosen)} Registro número {record_id}."
                records.append({"id": record_id, "text": text})
                record_id += 1
            member_name = f"mx_{file_idx:02d}.json"
            archive.writestr(
                member_name,
                json.dumps(records, ensure_ascii=False, indent=None),
            )


def get_hardware_specs() -> dict[str, Any]:
    """Obtiene las especificaciones del equipo de cómputo donde se ejecutan las pruebas."""
    specs: dict[str, Any] = {
        "os": f"{platform.system()} {platform.release()} ({platform.platform()})",
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "logical_cores": os.cpu_count() or 1,
        "physical_cores": os.cpu_count() or 1,
        "cpu_model": platform.processor() or "Desconocido",
        "ram_gb": "Desconocido",
    }

    if platform.system() == "Darwin":
        try:
            cpu_brand = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
            ).strip()
            if cpu_brand:
                specs["cpu_model"] = cpu_brand
            phys = subprocess.check_output(
                ["sysctl", "-n", "hw.physicalcpu"], text=True
            ).strip()
            logi = subprocess.check_output(
                ["sysctl", "-n", "hw.logicalcpu"], text=True
            ).strip()
            mem_bytes = int(
                subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            )
            specs["physical_cores"] = int(phys)
            specs["logical_cores"] = int(logi)
            specs["ram_gb"] = round(mem_bytes / (1024**3), 2)
        except Exception:
            pass
    return specs


def estimate_amdahl_fraction(speedup: float, p: int) -> float:
    """
    Despeja la fracción paralelizable `f` de la Ley de Amdahl:
      S(p) = 1 / ((1 - f) + f / p)
      => 1 / S(p) = 1 - f * (1 - 1/p)
      => f = (1 - 1 / S(p)) / (1 - 1 / p)
    """
    if p <= 1 or speedup <= 1.0:
        return 0.0
    f = (1.0 - (1.0 / speedup)) / (1.0 - (1.0 / p))
    return max(0.0, min(1.0, f))


def amdahl_theoretical_speedup(f: float, p: int) -> float:
    """Calcula el speedup teórico máximo según la Ley de Amdahl para `f` y `p`."""
    if p <= 1:
        return 1.0
    return 1.0 / ((1.0 - f) + (f / p))


def run_benchmarks(
    zip_path: Path,
    workers_list: list[int],
    repetitions: int = 3,
    batch_size: int = 1000,
    strategy: str = "auto",
) -> dict[str, Any]:
    """
    Ejecuta la versión secuencial y la versión paralela (`concurrent.futures`)
    para cada cantidad de procesos en `workers_list`, con `repetitions` repeticiones.
    Comprueba en cada corrida que el conteo paralelo coincida exactamente con el secuencial.
    """
    print(f"=== Iniciando experimentos sobre: {zip_path} ===")
    print(f"Repeticiones por configuración: {repetitions}")

    # 1. Medir versión secuencial base
    seq_times: list[float] = []
    seq_reference_counts = None

    for rep in range(1, repetitions + 1):
        start = time.perf_counter()
        counts = count_words_sequential(zip_path)
        elapsed = time.perf_counter() - start
        seq_times.append(elapsed)
        if seq_reference_counts is None:
            seq_reference_counts = counts
        elif counts != seq_reference_counts:
            raise AssertionError("Inconsistencia interna en corridas secuenciales")
        print(f"  [Secuencial] Repetición {rep}/{repetitions}: {elapsed:.4f} s")

    assert seq_reference_counts is not None
    t1_seq_mean = statistics.mean(seq_times)
    t1_seq_stdev = statistics.stdev(seq_times) if len(seq_times) > 1 else 0.0

    # 2. Medir versión paralela con concurrent.futures para cada número de procesos
    parallel_results: list[dict[str, Any]] = []

    for p in workers_list:
        p_times: list[float] = []
        for rep in range(1, repetitions + 1):
            start = time.perf_counter()
            par_counts = count_words_parallel(
                zip_path,
                workers=p,
                batch_size=batch_size,
                strategy=strategy,
            )
            elapsed = time.perf_counter() - start
            p_times.append(elapsed)

            # Verificación de correctitud obligatoria contra la referencia secuencial
            if par_counts != seq_reference_counts:
                raise AssertionError(
                    f"Error de correctitud con p={p}: el resultado paralelo no coincide con el secuencial."
                )
            print(
                f"  [Paralelo p={p}] Repetición {rep}/{repetitions}: {elapsed:.4f} s (Correctitud: OK)"
            )

        tp_mean = statistics.mean(p_times)
        tp_stdev = statistics.stdev(p_times) if len(p_times) > 1 else 0.0
        speedup = t1_seq_mean / tp_mean
        efficiency = speedup / p
        amdahl_f = estimate_amdahl_fraction(speedup, p)

        parallel_results.append(
            {
                "workers": p,
                "times": p_times,
                "mean_time": tp_mean,
                "stdev_time": tp_stdev,
                "speedup": speedup,
                "efficiency": efficiency,
                "amdahl_f": amdahl_f,
                "correct": True,
            }
        )

    # Estimar fracción paralelizable global (promedio de f para p > 1 con mayor ganancia)
    valid_f = [r["amdahl_f"] for r in parallel_results if r["workers"] > 1 and r["amdahl_f"] > 0]
    estimated_f_global = max(valid_f) if valid_f else 0.0

    for r in parallel_results:
        r["amdahl_speedup"] = amdahl_theoretical_speedup(estimated_f_global, r["workers"])

    return {
        "hardware": get_hardware_specs(),
        "dataset": {
            "zip_path": str(zip_path),
            "unique_words": len(seq_reference_counts),
            "total_words": sum(seq_reference_counts.values()),
            "top_20": seq_reference_counts.most_common(20),
        },
        "repetitions": repetitions,
        "sequential": {
            "times": seq_times,
            "mean_time": t1_seq_mean,
            "stdev_time": t1_seq_stdev,
        },
        "parallel_futures": parallel_results,
        "estimated_f_global": estimated_f_global,
    }


def save_results_and_plots(report: dict[str, Any], output_dir: Path) -> None:
    """Guarda los resultados en CSV, tabla Markdown y genera las gráficas PNG."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Guardar CSV
    csv_path = output_dir / "metrics_futures.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "version",
                "procesos_p",
                "tiempo_medio_s",
                "desv_estandar_s",
                "speedup",
                "eficiencia",
                "fraccion_paralela_f_amdahl",
                "speedup_teorico_amdahl",
                "correctitud",
            ]
        )
        seq = report["sequential"]
        writer.writerow(
            [
                "Secuencial (base)",
                1,
                f"{seq['mean_time']:.6f}",
                f"{seq['stdev_time']:.6f}",
                "1.0000",
                "1.0000",
                "-",
                "1.0000",
                "Referencia",
            ]
        )
        for row in report["parallel_futures"]:
            writer.writerow(
                [
                    "concurrent.futures",
                    row["workers"],
                    f"{row['mean_time']:.6f}",
                    f"{row['stdev_time']:.6f}",
                    f"{row['speedup']:.4f}",
                    f"{row['efficiency']:.4f}",
                    f"{row['amdahl_f']:.4f}" if row["workers"] > 1 else "-",
                    f"{row['amdahl_speedup']:.4f}",
                    "OK" if row["correct"] else "ERROR",
                ]
            )

    # Generar Gráfica 1: Tiempo vs. Número de procesos
    workers = [row["workers"] for row in report["parallel_futures"]]
    means = [row["mean_time"] for row in report["parallel_futures"]]
    stdevs = [row["stdev_time"] for row in report["parallel_futures"]]
    seq_mean = report["sequential"]["mean_time"]

    plt.figure(figsize=(8, 5))
    plt.axhline(
        y=seq_mean,
        color="#d95f02",
        linestyle="--",
        linewidth=1.8,
        label=f"Secuencial base ($T_1$ = {seq_mean:.3f} s)",
    )
    plt.errorbar(
        workers,
        means,
        yerr=stdevs,
        fmt="-o",
        color="#1b9e77",
        linewidth=2.2,
        markersize=7,
        capsize=5,
        label="Paralelo (concurrent.futures)",
    )
    plt.title("Tiempo de ejecución vs. Número de procesos (p)", fontsize=13, fontweight="bold")
    plt.xlabel("Número de procesos (p)", fontsize=11)
    plt.ylabel("Tiempo de ejecución (segundos)", fontsize=11)
    plt.xticks(workers)
    plt.grid(True, linestyle=":", alpha=0.7)
    plt.legend(fontsize=10)
    plt.tight_layout()
    time_plot_path = output_dir / "tiempo_vs_procesos.png"
    plt.savefig(time_plot_path, dpi=180)
    plt.close()

    # Generar Gráfica 2: Speedup Real vs. Ideal vs. Ley de Amdahl
    speedups = [row["speedup"] for row in report["parallel_futures"]]
    amdahl_curve = [row["amdahl_speedup"] for row in report["parallel_futures"]]
    f_global = report["estimated_f_global"]

    plt.figure(figsize=(8, 5))
    plt.plot(
        workers,
        workers,
        linestyle="--",
        color="#7570b3",
        linewidth=1.8,
        label="Speedup Ideal ($S(p) = p$)",
    )
    if f_global > 0:
        plt.plot(
            workers,
            amdahl_curve,
            linestyle="-.",
            color="#e7298a",
            linewidth=1.8,
            label=f"Cota Ley de Amdahl ($f \\approx {f_global:.3f}$)",
        )
    plt.plot(
        workers,
        speedups,
        marker="s",
        color="#1b9e77",
        linewidth=2.2,
        markersize=7,
        label="Speedup Real (concurrent.futures)",
    )
    plt.title("Speedup Real vs. Speedup Ideal y Ley de Amdahl", fontsize=13, fontweight="bold")
    plt.xlabel("Número de procesos (p)", fontsize=11)
    plt.ylabel("Speedup $S(p) = T_1 / T_p$", fontsize=11)
    plt.xticks(workers)
    plt.grid(True, linestyle=":", alpha=0.7)
    plt.legend(fontsize=10)
    plt.tight_layout()
    speedup_plot_path = output_dir / "speedup_vs_ideal.png"
    plt.savefig(speedup_plot_path, dpi=180)
    plt.close()

    # Generar Gráfica 3: Eficiencia vs. Número de procesos
    efficiencies = [row["efficiency"] for row in report["parallel_futures"]]
    plt.figure(figsize=(8, 5))
    plt.axhline(y=1.0, color="#7570b3", linestyle="--", linewidth=1.8, label="Eficiencia Ideal (100%)")
    plt.plot(
        workers,
        efficiencies,
        marker="^",
        color="#d95f02",
        linewidth=2.2,
        markersize=7,
        label="Eficiencia Real $E(p) = S(p)/p$",
    )
    plt.title("Eficiencia Paralela vs. Número de procesos (p)", fontsize=13, fontweight="bold")
    plt.xlabel("Número de procesos (p)", fontsize=11)
    plt.ylabel("Eficiencia $E(p)$", fontsize=11)
    plt.xticks(workers)
    plt.ylim(0, max(1.15, max(efficiencies) + 0.1))
    plt.grid(True, linestyle=":", alpha=0.7)
    plt.legend(fontsize=10)
    plt.tight_layout()
    eff_plot_path = output_dir / "eficiencia_vs_procesos.png"
    plt.savefig(eff_plot_path, dpi=180)
    plt.close()

    print(f"\nResultados guardados en: {output_dir}")
    print(f"  - {csv_path}")
    print(f"  - {time_plot_path}")
    print(f"  - {speedup_plot_path}")
    print(f"  - {eff_plot_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta las mediciones de rendimiento secuencial vs. concurrent.futures "
            "para 1, 2, 4 y 8 procesos con múltiples repeticiones y genera tablas y gráficas."
        )
    )
    parser.add_argument(
        "zip_path",
        nargs="?",
        type=Path,
        default=Path("data/mx.zip"),
        help="Ruta al archivo ZIP del dataset (predeterminado: data/mx.zip)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        nargs="+",
        default=[1, 2, 4, 8],
        help="Lista de números de procesos a evaluar (predeterminado: 1 2 4 8)",
    )
    parser.add_argument(
        "--repetitions",
        "-r",
        type=int,
        default=3,
        help="Número de repeticiones por configuración (predeterminado: 3, mínimo recomendado: 3)",
    )
    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=1000,
        help="Tamaño de lote para reparto por lotes (predeterminado: 1000)",
    )
    parser.add_argument(
        "--strategy",
        choices=["auto", "members", "batches"],
        default="auto",
        help="Estrategia de reparto paralelo (predeterminado: auto)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("resultados"),
        help="Directorio donde se guardarán las métricas y gráficas (predeterminado: resultados)",
    )
    parser.add_argument(
        "--generate-if-missing",
        action="store_true",
        default=True,
        help="Generar un dataset sintético realista si zip_path no existe",
    )
    parser.add_argument(
        "--num-files",
        type=int,
        default=16,
        help="Cantidad de archivos JSON al generar dataset sintético (predeterminado: 16)",
    )
    parser.add_argument(
        "--records-per-file",
        type=int,
        default=5000,
        help="Registros por archivo JSON al generar dataset sintético (predeterminado: 5000)",
    )
    args = parser.parse_args()

    if not args.zip_path.is_file():
        if args.generate_if_missing:
            print(
                f"No se encontró {args.zip_path}. Generando dataset sintético "
                f"({args.num_files} archivos JSON x {args.records_per_file} registros)..."
            )
            generate_synthetic_mx_zip(
                args.zip_path,
                num_files=args.num_files,
                records_per_file=args.records_per_file,
            )
        else:
            raise FileNotFoundError(f"No se encontró el archivo: {args.zip_path}")

    report = run_benchmarks(
        zip_path=args.zip_path,
        workers_list=args.workers,
        repetitions=args.repetitions,
        batch_size=args.batch_size,
        strategy=args.strategy,
    )
    save_results_and_plots(report, args.output_dir)


if __name__ == "__main__":
    main()
