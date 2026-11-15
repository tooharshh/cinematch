#!/usr/bin/env python3
"""Read-only smoke checks against the running capstone containers (standard library only)."""
import json
import subprocess
import urllib.error
import urllib.request


def request(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request('http://127.0.0.1:8000' + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


health = request('/health')
assert health['status'] == 'ready' and health['movies'] > 0
# Choose an available title rather than assume a live snapshot contains Inception.
remote = subprocess.check_output([
    'podman', 'exec', 'backend', 'python', '-c',
    'from app.recommender import get_catalog; import json; c=get_catalog(); print(json.dumps(c.details(0)))'
], text=True)
movie = json.loads(remote)
result = request('/recommendations/', {'movie': movie['title'], 'movie_id': movie['id']})
details = result['recommendation_details']
assert len(details) == min(5, health['movies'] - 1)
assert movie['id'] not in [m['id'] for m in details]
assert len({m['id'] for m in details}) == len(details)
assert [m['similarity'] for m in details] == sorted(
    [m['similarity'] for m in details], reverse=True)
try:
    request('/recommendations/', {'movie': '__definitely_not_in_catalog_23984__'})
    raise AssertionError('Unavailable title should return 404')
except urllib.error.HTTPError as exc:
    assert exc.code == 404
subprocess.run(['podman', 'exec', 'frontend', 'python', '-c',
                "import requests; r=requests.get('http://backend:8000/health', timeout=5); r.raise_for_status(); print(r.json())"], check=True)
with urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=5) as response:
    assert response.status == 200
containers = json.loads(subprocess.check_output(
    ['podman', 'inspect', 'backend', 'frontend'], text=True))
for container in containers:
    assert container['Config']['User'] == 'appuser'
    assert 'siw-net' in container['NetworkSettings']['Networks']
    assert not any(key.startswith('API_KEY=') for key in container['Config']['Env'])
backend = next(c for c in containers if c['Name'].lstrip('/') == 'backend')
assert any(m['Destination'] == '/data' and not m['RW'] for m in backend['Mounts'])
print('PASS: API, ranking, invalid-title handling, UI health, DNS, non-root users, secret isolation and read-only storage')
