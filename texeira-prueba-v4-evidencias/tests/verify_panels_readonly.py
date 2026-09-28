"""Read-only production HTML/auth checks. No POST, DB access or outbound messages."""
import base64
import subprocess
import urllib.request
import urllib.error

BASE = 'https://texeira-whatsapp-1038134693816.us-central1.run.app'
GCLOUD = r'C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'

def get(path, headers=None):
    request = urllib.request.Request(BASE + path, headers=headers or {})
    # Reject redirects rather than forwarding credentials to another origin.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as error:
        return error.code, ''

if __name__ == '__main__':
    result = subprocess.run([GCLOUD, 'secrets', 'versions', 'access', '2',
        '--secret=ADMIN_PASSWORD', '--project=texeira-whatsapp-bot'], capture_output=True, text=True, check=True)
    password = result.stdout.strip()
    assert password, 'Missing admin credential'
    headers = {'Authorization': 'Basic ' + base64.b64encode(('admin:' + password).encode()).decode()}
    for path, marker in [('/handoffs','ticketSearch'),('/catalogo','tourModal'),
                         ('/dashboard','Resumen de interacciones'),('/operational-metrics','rows-traffic')]:
        status, _ = get(path)
        assert status == 401, (path, 'unauthenticated', status)
        status, html = get(path, headers)
        assert status == 200 and 'admin-nav' in html and marker in html, (path, 'authenticated', status)
        print(f'PASS {path}: 401 without auth; 200 and updated markup with auth', flush=True)
