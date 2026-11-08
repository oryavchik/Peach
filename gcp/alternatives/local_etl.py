"""Free Dataflow substitute: local transform of real public BigQuery output.

Produces JSONL suitable for a BigQuery batch load, without GCS or workers.
"""
import csv
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/lab9-evidence'


def main():
    source = list(csv.DictReader((OUT / 'bigquery-results.csv').open()))
    total = sum(int(row['total_words']) for row in source)
    assert total > 0
    rows = [{'corpus': row['corpus'], 'total_words': int(row['total_words']),
             'distinct_words': int(row['distinct_words']),
             'share_of_words': int(row['total_words']) / total}
            for row in source]
    assert len({r['corpus'] for r in rows}) == len(rows) == 42
    assert abs(sum(r['share_of_words'] for r in rows) - 1) < 1e-12
    (OUT / 'etl-output.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    (OUT / 'local-etl.json').write_text(json.dumps({
        'engine': 'Python CSV to JSONL batch transform', 'is_dataflow': False,
        'input_rows': len(source), 'output_rows': len(rows),
        'total_words': total, 'share_sum_verified': True,
        'source': 'Actual public BigQuery Shakespeare query result',
        'transform': 'Convert integer types and compute share_of_words',
    }, indent=2) + '\n')
    print('42 public rows transformed; normalized shares verified')


if __name__ == '__main__':
    main()
