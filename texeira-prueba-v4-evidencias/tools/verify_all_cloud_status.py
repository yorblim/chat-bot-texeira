import subprocess
import json

def run(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.stdout.strip()

print("--- 1. CLOUD STORAGE BUCKET ---")
bucket_items = run("gcloud storage ls gs://run-sources-texeira-whatsapp-bot-us-central1")
print(f"Archivos en bucket: {len(bucket_items.splitlines()) if bucket_items else 0}")
lifecycle = run("gcloud storage buckets describe gs://run-sources-texeira-whatsapp-bot-us-central1 --format='yaml(lifecycle_config)'")
print("Regla de ciclo de vida:")
print(lifecycle)

print("\n--- 2. ARTIFACT REGISTRY ---")
images = run("gcloud artifacts docker images list us-central1-docker.pkg.dev/texeira-whatsapp-bot/cloud-run-source-deploy/texeira-whatsapp --project=texeira-whatsapp-bot --format='table(DIGEST.slice(0:19),TAGS,CREATE_TIME)'")
print("Imágenes en Artifact Registry:")
print(images)
policies = run("gcloud artifacts repositories describe cloud-run-source-deploy --location=us-central1 --project=texeira-whatsapp-bot --format='yaml(cleanupPolicies)'")
print("Políticas de retención:")
print(policies)

print("\n--- 3. SECRET MANAGER ---")
secrets = run("gcloud secrets list --project=texeira-whatsapp-bot --format='value(name)'").splitlines()
print(f"Total secretos: {len(secrets)}")
for s in secrets:
    versions = run(f"gcloud secrets versions list {s} --project=texeira-whatsapp-bot --filter='STATE=ENABLED' --format='value(name)'").splitlines()
    print(f"  Secret {s}: {len(versions)} versión activa")

print("\n--- 4. CLOUD RUN SERVICE ---")
cr_status = run("gcloud run services describe texeira-whatsapp --region=us-central1 --project=texeira-whatsapp-bot --format='yaml(status.url,status.conditions[0].status,spec.template.metadata.annotations[\"autoscaling.knative.dev/minScale\"])'")
print(cr_status)

print("\n--- 5. ESTADO DE FACTURACION PROYECTO SECUNDARIO ---")
billing_sec = run("gcloud billing projects describe gen-lang-client-0359389066 --format='yaml(billingEnabled)'")
print(billing_sec)

