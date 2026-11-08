"""Verify the free Lab9 substitute without AI calls or exporting user data."""
import json
from urllib.request import Request
from smoke import ROOT, URL, call, opener


def main():
    values = {line.partition('=')[0]: line.partition('=')[2].strip().strip('\"\'')
              for line in (ROOT / '.env').read_text().splitlines()
              if '=' in line and not line.startswith('#')}
    evidence = {'date': '2026-11-08', 'url': URL, 'substitute': 'Cloudflare Workers Static Assets + Workers + D1', 'is_gcp_core': False}
    for path in ['/home', '/items', '/meetings']:
        with opener.open(Request(URL + path, headers={'User-Agent': 'PeachLabSmoke/1.0'}), timeout=30) as response:
            assert response.status == 200 and b'<html' in response.read().lower()
    evidence['frontend_pages_http_200'] = True
    status, _ = call('/api/v1/items')
    assert status == 401, status
    evidence['unsigned_items_status'] = status
    status, _ = call('/api/login', {'password': values['CLOUDFLARE_DEMO_PASSWORD']})
    assert status == 200, status
    status, ready = call('/api/v1/health/ready')
    assert status == 200 and ready['database'] == 'ok'
    evidence['database_ready'] = ready
    status, item = call('/api/v1/items', {'name': 'Lab9 free substitute smoke', 'description': 'Synthetic temporary verification', 'status': 'todo'})
    assert status == 201, status
    try:
        status, rows = call('/api/v1/items?limit=100')
        assert status == 200 and any(row['id'] == item['id'] and row['name'] == item['name'] for row in rows['items'])
        evidence['database_create_then_list_read'] = True
    finally:
        request = Request(URL + '/api/v1/items/' + item['id'], method='DELETE', headers={'Origin': URL, 'User-Agent': 'PeachLabSmoke/1.0'})
        with opener.open(request, timeout=30) as response:
            assert response.status == 204
        evidence['synthetic_item_deleted'] = True
    evidence['ai_called'] = False
    evidence['personal_data_exported'] = False
    (ROOT / 'docs/lab9-evidence/cloudflare-core-check.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
