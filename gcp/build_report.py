"""Build an honest, standalone HTML report from saved evidence (no network)."""
import csv
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / 'docs/lab9-evidence'
OUT = ROOT / 'docs/lab9-submit'


def table(rows):
    keys = list(rows[0])
    return '<table><thead><tr>' + ''.join(f'<th>{html.escape(k)}</th>' for k in keys) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{html.escape(str(row[k]))}</td>' for k in keys) + '</tr>' for row in rows) + '</tbody></table>'


def main():
    costs = list(csv.DictReader((E / 'cost-profiles.csv').open()))
    results = list(csv.DictReader((E / 'bigquery-results.csv').open()))
    job = json.loads((E / 'bigquery-job.json').read_text())
    assert job['status']['state'] == 'DONE' and not job['status'].get('errorResult')
    assert len(results) == 42 and sum(int(r['total_words']) for r in results) > 0
    chart = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 440" role="img" aria-label="Top ten Shakespeare corpora by total words">'
    maximum = max(int(r['total_words']) for r in results)
    for i, row in enumerate(results[:10]):
        y = 20 + i * 41
        width = int(row['total_words']) / maximum * 580
        chart += f'<text x="0" y="{y+18}" font-size="14">{html.escape(row["corpus"])}</text><rect x="155" y="{y}" width="{width}" height="28" fill="#287b8e"/><text x="{165+width}" y="{y+18}" font-size="13">{row["total_words"]}</text>'
    chart += '</svg>'
    (OUT / 'bigquery-chart.svg').write_text(chart)
    smoke_path = E / 'firestore-smoke.json'
    smoke = json.loads(smoke_path.read_text()) if smoke_path.exists() else {'write_read_equal': False}
    sections = '<h2>Firestore REST smoke test</h2><pre>' + html.escape(json.dumps(smoke, ensure_ascii=False, indent=2)) + '</pre>'
    body = '''<h1>Lab 9 — Google Cloud / Peach</h1><p>Перевірено 8 листопада 2026. Без billing і trial.</p>
<p><strong>Частково виконано.</strong> Немає розгорнутого Cloud Run/FastAPI, Firebase Hosting, Looker/OCR screenshots, Vertex/Dataflow runs або provider calculator exports. Цей документ не заявляє повного виконання лабораторної.</p>
<p>Terraform та ADR підготовлені. BigQuery запит реально виконаний. Firestore створена як free tier. Firebase повертає 403. Доступ до керування браузером відсутній.</p>
<h2>BigQuery: реальні результати</h2><p>Job peach_lab9_public_20261107_01, US; 42 рядки; 3 781 873 bytes processed. Графік нижче локальний, із збереженого CSV; це не скриншот Looker Studio.</p>'''
    body += '<pre>' + html.escape(job['configuration']['query']['query']) + '</pre>' + chart + table(results) + sections
    body += '<h2>Чотири профілі вартості, USD</h2><p>Модель за ставками завдання; нижня межа, не фактичний рахунок і не результат provider calculators. Детальні припущення та відповіді наведені нижче.</p>' + table(costs)
    answers = (OUT / 'ANSWERS.md').read_text()
    body += '<h2>Відповіді та відтворення</h2><pre>' + html.escape(answers) + '</pre>'
    document = '<!doctype html><html lang="uk"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Lab 9 — Google Cloud / Peach</title><style>body{font:16px/1.6 system-ui;color:#173047;max-width:1150px;margin:40px auto;padding:0 24px}table{border-collapse:collapse;font-size:12px;display:block;overflow:auto}td,th{padding:8px;border:1px solid #ccd9df;text-align:left}th{background:#e8f1f5}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f7;padding:20px}svg{width:100%;height:auto}h2{margin-top:40px}</style>' + body + '</html>'
    (OUT / 'Lab9_report.html').write_text(document)
    print('Report generated; 42 BigQuery rows verified; Firestore write/read:', smoke['write_read_equal'])


if __name__ == '__main__':
    main()
