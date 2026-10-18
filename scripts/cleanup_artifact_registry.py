"""scripts/cleanup_artifact_registry.py — Limpieza inmediata de imágenes obsoletas en Artifact Registry.

Conserva las 2 imágenes más recientes (incluyendo la activa en Cloud Run)
y elimina todas las imágenes anteriores que consumen almacenamiento.
"""
import os
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO_BASE = "us-central1-docker.pkg.dev/texeira-whatsapp-bot/cloud-run-source-deploy/texeira-whatsapp"
GCLOUD_CMD = r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"


def run_cmd(cmd_list):
    res = subprocess.run(cmd_list, capture_output=True, text=True)
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def delete_image(digest):
    full_target = f"{REPO_BASE}@{digest}"
    code, out, err = run_cmd([
        GCLOUD_CMD, "artifacts", "docker", "images", "delete",
        full_target, "--quiet", "--delete-tags"
    ])
    return digest, code == 0, err if code != 0 else ""


def main():
    print("=" * 70)
    print("  LIMPIEZA DE IMÁGENES OBSOLETAS EN ARTIFACT REGISTRY")
    print("=" * 70)

    # 1. Obtener imagen activa en Cloud Run
    print("\n[1/4] Verificando imagen activa en Cloud Run...")
    code, active_image, _ = run_cmd([
        GCLOUD_CMD, "run", "services", "describe", "texeira-whatsapp",
        "--region=us-central1", "--project=texeira-whatsapp-bot",
        "--format=value(spec.template.spec.containers[0].image)"
    ])
    active_digest = active_image.split("@")[-1] if "@" in active_image else ""
    print(f"  Imagen activa actual: {active_digest[:24]}...")

    # 2. Listar todas las imágenes ordenadas por fecha descendente
    print("\n[2/4] Consultando imágenes en Artifact Registry...")
    code, stdout, _ = run_cmd([
        GCLOUD_CMD, "artifacts", "docker", "images", "list",
        REPO_BASE, "--project=texeira-whatsapp-bot",
        "--sort-by=~CREATE_TIME", "--format=value(DIGEST)"
    ])
    all_digests = [d.strip() for d in stdout.splitlines() if d.strip().startswith("sha256:")]
    total = len(all_digests)
    print(f"  Total de imágenes encontradas: {total}")

    if total <= 2:
        print("  [OK] El repositorio ya tiene 2 o menos imagenes. No hay nada que limpiar.")
        return

    # 3. Conservar las 2 más recientes (y asegurar que la activa nunca se elimine)
    keep_digests = set(all_digests[:2])
    if active_digest:
        keep_digests.add(active_digest)

    to_delete = [d for d in all_digests if d not in keep_digests]
    print(f"\n[3/4] Se conservarán {len(keep_digests)} imágenes recientes de respaldo.")
    print(f"      Se eliminarán {len(to_delete)} imágenes obsoletas (~{(len(to_delete) * 3.8):.1f} GB de espacio)...")

    # 4. Eliminar en paralelo con 4 hilos para mayor velocidad
    print("\n[4/4] Eliminando imágenes obsoletas...")
    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(delete_image, d): d for d in to_delete}
        for i, future in enumerate(as_completed(futures), 1):
            digest, ok, err = future.result()
            if ok:
                success_count += 1
                print(f"  [{i}/{len(to_delete)}] Eliminada: {digest[:20]}... [OK]")
            else:
                fail_count += 1
                print(f"  [{i}/{len(to_delete)}] Error en {digest[:20]}...: {err} [ERROR]")

    print("\n" + "=" * 70)
    print(f"  LIMPIEZA FINALIZADA:")
    print(f"  - Eliminadas con éxito: {success_count}")
    print(f"  - Errores: {fail_count}")
    print(f"  - Espacio aproximado liberado: ~{(success_count * 3.8):.1f} GB")
    print("=" * 70)


if __name__ == "__main__":
    main()
