import subprocess
import os
import tempfile

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'

updates = {
    'META_ACCESS_TOKEN': 'EAAT52KsZBIywBSajZBzCmXw77ahOXw8eCzROEo9ov5eOaZAxS1ZAZBwSfxdU9fOCeSdWVWE8IFjBZCeIwWZAmH8ZA9GuMauWiVpyf22zHBNPA2zuoC6AAfxOeq2YQRovPXIgSUbnHWzTVfeGGhoiWP8WZC3mRsOJfitnFgHOr638JZCQF5kZCZBuo6ffxImGeb3BH18ZAdS9rHMX0eyrjJ3hUpvnzXcZBZBtd6WHt4gtrDCi1NoCZC4eAlVFxIa35jhDU9MPqL7z7OayzttBYo4WTKfL7RZB9',
}

for secret_name, new_value in updates.items():
    clean_bytes = new_value.strip().encode('utf-8')
    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as tmp:
        tmp.write(clean_bytes)
        tmp_path = tmp.name
    try:
        cmd = f'gcloud secrets versions add {secret_name} --data-file="{tmp_path}" --project=texeira-whatsapp-bot'
        res = subprocess.run(cmd, shell=True, capture_output=True, env=env)
        if res.returncode == 0:
            print(f'{secret_name}: actualizado OK (len={len(clean_bytes)})')
        else:
            print(f'{secret_name}: ERROR -> {res.stderr.decode("utf-8", errors="ignore")}')
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
