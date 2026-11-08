"""One synthetic free-model call instead of Vertex AI Studio; no database write."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'cloudflare'))
from smoke import call


def main():
    values = {line.partition('=')[0]: line.partition('=')[2].strip().strip('\"\'')
              for line in (ROOT / '.env').read_text().splitlines()
              if '=' in line and not line.startswith('#')}
    status, _ = call('/api/login', {'password': values['CLOUDFLARE_DEMO_PASSWORD']})
    assert status == 200
    fixture = json.loads((ROOT / 'docs/ai-evidence/inputs.json').read_text())[1]
    status, response = call('/api/parse', {key: fixture[key] for key in ['text', 'today', 'tz']})
    evidence = {'date': '2026-11-08', 'is_vertex_ai': False, 'status': status,
                'synthetic_input': {key: fixture[key] for key in ['text', 'today', 'tz']},
                'response': response, 'database_write': False}
    (ROOT / 'docs/lab9-evidence/free-agenda-demo.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    assert status == 200, 'Free provider unavailable; see saved failure evidence'
    assert response['model'].endswith(':free') and response['cost_usd'] == 0
    print('Synthetic free agenda call verified; no database write')


if __name__ == '__main__':
    main()
