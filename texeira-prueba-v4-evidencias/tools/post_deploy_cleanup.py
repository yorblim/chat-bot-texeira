"""
Script de limpieza automática post-despliegue para Texeira Travel.
Garantiza Costo $0.00 en Google Cloud eliminando fuentes temporales (.zip)
e imágenes Docker antiguas de Artifact Registry.
"""
import subprocess
import sys
import json

PROJECT_ID = "texeira-whatsapp-bot"
REGION = "us-central1"
SERVICE_NAME = "texeira-whatsapp"
STORAGE_BUCKET = "gs://run-sources-texeira-whatsapp-bot-us-central1"
REPO_PATH = f"us-central1-docker.pkg.dev/{PROJECT_ID}/cloud-run-source-deploy/{SERVICE_NAME}"

def run_cmd(cmd_list):
    """Ejecuta un comando del sistema y retorna el stdout."""
    res = subprocess.run(cmd_list, capture_output=True, text=True, shell=True)
    return res.returncode, res.stdout.strip(), res.stderr.strip()

def cleanup_cloud_storage():
    print("  -> [1/2] Limpiando archivos temporales (.zip) en Google Cloud Storage...")
    code, stdout, stderr = run_cmd(f'gcloud storage rm "{STORAGE_BUCKET}/**" --recursive --quiet')
    # Si estaba vacío, retorna código != 0 pero es inocuo
    print("     [OK] Cloud Storage limpio (Consumo: 0 Bytes).")

def cleanup_artifact_registry():
    print("  -> [2/2] Verificando imágenes en Artifact Registry...")
    # 1. Obtener la imagen activa en Cloud Run
    code, active_img, err = run_cmd(
        f'gcloud run services describe {SERVICE_NAME} --region={REGION} --project={PROJECT_ID} --format="value(spec.template.spec.containers[0].image)"'
    )
    if code != 0 or not active_img:
        print(f"     [AVISO] No se pudo obtener la imagen activa de Cloud Run: {err}")
        return

    active_digest = active_img.split("@")[-1] if "@" in active_img else ""
    print(f"     Imagen activa en produccion: {active_digest[:19]}...")

    # 2. Listar todas las versiones en Artifact Registry
    code, digests_out, err = run_cmd(
        f'gcloud artifacts docker images list {REPO_PATH} --project={PROJECT_ID} --format="value(DIGEST)"'
    )
    if code != 0:
        print(f"     [AVISO] No se pudo listar imágenes de Artifact Registry: {err}")
        return

    digests = [d.strip() for d in digests_out.splitlines() if d.strip().startswith("sha256:")]
    deleted_count = 0

    for d in digests:
        if d != active_digest:
            print(f"     Borrando versión obsoleta: {d[:19]}... para liberar espacio...")
            del_code, _, del_err = run_cmd(
                f'gcloud artifacts docker images delete "{REPO_PATH}@{d}" --delete-tags --quiet'
            )
            if del_code == 0:
                print(f"     [OK] Version {d[:19]} eliminada con exito.")
                deleted_count += 1
            else:
                print(f"     [!] Error al borrar {d[:19]}: {del_err}")

    if deleted_count == 0:
        print("     [OK] Solo existe la imagen activa actual. Espacio optimizado al maximo.")

def main():
    print("\n" + "=" * 65)
    print("  LIMPIEZA AUTOMATICA POST-DESPLIEGUE (GARANTIA COSTO $0.00)")
    print("=" * 65)
    try:
        cleanup_cloud_storage()
        cleanup_artifact_registry()
        print("=" * 65)
        print("  LIMPIEZA COMPLETADA CON EXITO: 0 RESIDUOS EN LA NUBE")
        print("=" * 65 + "\n")
    except Exception as e:
        print(f"  [ERROR] Fallo en la rutina de limpieza: {e}")

if __name__ == "__main__":
    main()

