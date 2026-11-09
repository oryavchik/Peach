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
    body = '''<h1>Lab 9 — Google Cloud / Peach: безкоштовні заміни</h1><p>Оновлено 9 листопада 2026. Без GCP billing і trial.</p>
<p>Код опубліковано: <a href="https://github.com/oryavchik/Peach/tree/lab9-free-substitutions">GitHub Lab 9</a>. <a href="https://github.com/oryavchik/Peach/commit/41fa5a17">Terraform + ADR commit</a>; <a href="https://github.com/oryavchik/Peach/commit/0dea3843">безкоштовні заміни commit</a>.</p>
<p><strong>Робочий альтернативний застосунок:</strong> <a href="https://peach-agenda-free.peach-free-cloud-demo.workers.dev/">Peach на Cloudflare</a>. Static Assets + Workers + D1 замінюють Firebase Hosting + Cloud Run + Cloud SQL. Це відхилення від умови, а не GCP core deployment. Google BigQuery та Firestore виконані окремо.</p>
<p><strong>Частково виконано.</strong> Немає розгорнутого Cloud Run/FastAPI, Firebase Hosting, Google OCR screenshots, Vertex/Dataflow runs або provider calculator exports. Цей документ не заявляє повного виконання лабораторної.</p>
<p>Terraform та ADR підготовлені. BigQuery запит реально виконаний. Firestore створена як free tier. Firebase повертає 403. Доступ до керування браузером відсутній.</p>
<h2>BigQuery: реальні результати</h2><p>Job peach_lab9_public_20261107_01, US; 42 рядки; 3 781 873 bytes processed. Графік нижче локальний, із збереженого CSV; це не скриншот Looker Studio.</p>'''
    body += '<pre>' + html.escape(job['configuration']['query']['query']) + '</pre>' + chart + table(results) + sections
    fresh_job_path = E / 'bigquery-job-20261109.json'
    if fresh_job_path.exists():
        fresh_job = json.loads(fresh_job_path.read_text())
        assert fresh_job['status']['state'] == 'DONE' and not fresh_job['status'].get('errorResult')
        body += '<h2>BigQuery: свіжа перевірка 2026-11-09</h2><p>Job peach_lab9_public_20261109_01, 42 рядки; processed bytes: ' + html.escape(str(fresh_job['statistics']['query']['totalBytesProcessed'])) + '. Таблиця word_counts_20261109 має 48h expiry. CSV підготовлено для Looker File Upload.</p>'
        body += '<p>Native BigQuery connector Looker потребує billing project; для no-billing використовується CSV export. Data Studio chart створено користувачем і підтверджено скриншотами в розмові; джерело — CSV із BigQuery. Browser host недоступний, Safari Computer Use timeout. Firebase API досі 403 попри наявну project Owner role; можливий неприйнятий Firebase Terms, точну причину API не повернув.</p>'
    looker_path = E / 'looker-report.json'
    if looker_path.exists():
        looker = json.loads(looker_path.read_text())
        body += '<h2>Data Studio: виконаний графік</h2><p><a href="' + html.escape(looker['url'], quote=True) + '">Peach Lab 9 — BigQuery results</a>. Top 10 corpus, SUM(total_words), descending. Джерело — CSV export справжнього BigQuery result. Підтверджено скриншотами користувача в розмові; доступ викладача за посиланням ще потрібно перевірити. Файл скриншота до репозиторію не доданий.</p>'
    cost_final = OUT / 'COST_FINAL.md'
    if cost_final.exists():
        body += '<h2>Фінальна таблиця калькуляторів</h2><pre>' + html.escape(cost_final.read_text()) + '</pre>'
    aws_path = E / 'aws-calculator-baseline.json'
    if aws_path.exists():
        aws = json.loads(aws_path.read_text())
        body += '<h2>AWS Calculator: базова оцінка</h2><p><a href="' + html.escape(aws['url'], quote=True) + '">Відкрити estimate</a>. $43.90/month: Aurora 0.5 ACU always-on + 1 GB storage; Lambda 0 requests. Це базовий always-on reference; ручні поправки та інші профілі наведені у фінальній таблиці.</p>'
    busy_path = E / 'aws-calculator-busy.json'
    if busy_path.exists():
        busy = json.loads(busy_path.read_text())
        body += '<h2>AWS Calculator: busy 24/7</h2><p><a href="' + html.escape(busy['url'], quote=True) + '">Відкрити estimate</a>. Lambda $0.33 + Aurora $43.90 = $44.23/month. Підтверджено скриншотом користувача; Підсумок усіх профілів і обмеження наведені у фінальній таблиці.</p>'
    cloud_run_path = E / 'gcp-calculator-cloud-run.json'
    if cloud_run_path.exists():
        cloud_run = json.loads(cloud_run_path.read_text())
        body += '<h2>GCP Calculator: Cloud Run reference</h2><p><a href="' + html.escape(cloud_run['url'], quote=True) + '">Відкрити estimate</a>. $6.51/month: CPU $6.00, memory $0.31, requests $0.20. 2.5M requests, а не 2.628M точної моделі. База даних ще не включена; free-quota-adjusted model наведена окремо.</p>'
    core_path = E / 'gcp-calculator-busy-core.json'
    if core_path.exists():
        core = json.loads(core_path.read_text())
        body += '<h2>GCP Calculator: busy core reference</h2><p><a href="' + html.escape(core['url'], quote=True) + '">Відкрити estimate</a>. Cloud Run $6.51 + Firestore $1.12 = $7.63/month. Cloud Run request preset і врахування free tier відрізняються від точної моделі. Усі GCP reference links збережено.</p>'
    office_path = E / 'gcp-calculator-office.json'
    if office_path.exists():
        office = json.loads(office_path.read_text())
        body += '<h2>GCP Calculator: office hours approximation</h2><p><a href="' + html.escape(office['url'], quote=True) + '">Відкрити estimate</a>. Cloud Run $1.26 + Firestore $0.07 = $1.33/month. Cloud Run 500000 requests замість точних 633600; Firestore daily rate за весь місяць, а не 22 активні дні.</p>'
    demo_path = E / 'gcp-calculator-demo.json'
    if demo_path.exists():
        demo = json.loads(demo_path.read_text())
        body += '<h2>GCP Calculator: class demos approximation</h2><p><a href="' + html.escape(demo['url'], quote=True) + '">Відкрити estimate</a>. Cloud Run $0.25 + Firestore $0.00 = $0.25/month. Cloud Run 100000 requests замість точних 72000; точна модель та calculator free-quota treatment наведені окремо.</p>'
    idle_path = E / 'gcp-calculator-idle.json'
    if idle_path.exists():
        idle = json.loads(idle_path.read_text())
        body += '<h2>GCP Calculator: idle reference</h2><p><a href="' + html.escape(idle['url'], quote=True) + '">Відкрити estimate</a>. Cloud Run $0.00 + Firestore $0.00 = $0.00/month. Firestore positive technical minimum замість нульових операцій; фінальні operation inputs не видно на скриншоті. Чотири GCP reference links збережено, із задокументованими наближеннями.</p>'
    aws_office_path = E / 'aws-calculator-office.json'
    if aws_office_path.exists():
        aws_office = json.loads(aws_office_path.read_text())
        body += '<h2>AWS Calculator: office / Aurora always-on reference</h2><p><a href="' + html.escape(aws_office['url'], quote=True) + '">Відкрити estimate</a>. Lambda $0.00 + Aurora always-on $43.90. Ручна корекція Aurora до 176h: $10.66 core без додаткових I/O; це не total із calculator.</p>'
    for filename, title in [
        ('cloudflare-core-check.json', 'Робочий безкоштовний core: реальна перевірка'),
        ('local-ocr.json', 'Заміна Google OCR: Apple Vision, локально'),
        ('local-etl.json', 'Заміна Dataflow: локальний ETL'),
        ('etl-bigquery-verification.json', 'Реальне завантаження ETL у Google BigQuery'),
        ('free-agenda-demo.json', 'Заміна Vertex: безкоштовна agenda модель'),
    ]:
        path = E / filename
        if path.exists():
            value = json.loads(path.read_text())
            body += '<h2>' + html.escape(title) + '</h2>'
            if filename == 'local-ocr.json':
                import base64
                encoded = base64.b64encode((E / 'synthetic-receipt.png').read_bytes()).decode()
                body += f'<img alt="Синтетичний чек для локального OCR" style="max-width:650px;width:100%" src="data:image/png;base64,{encoded}">'
            body += '<pre>' + html.escape(json.dumps(value, ensure_ascii=False, indent=2)) + '</pre>'
    body += '<h2>Чотири профілі вартості, USD</h2><p>Модель за ставками завдання; нижня межа, не фактичний рахунок і не результат provider calculators. Детальні припущення та відповіді наведені нижче.</p>' + table(costs)
    answers = (OUT / 'ANSWERS.md').read_text()
    body += '<h2>Відповіді та відтворення</h2><pre>' + html.escape(answers) + '</pre>'
    browser_steps = OUT / 'BROWSER_FINISH.md'
    if browser_steps.exists():
        body += '<h2>Підготовлено для завершення через браузер</h2><pre>' + html.escape(browser_steps.read_text()) + '</pre>'
    document = '<!doctype html><html lang="uk"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Lab 9 — Google Cloud / Peach</title><style>body{font:16px/1.6 system-ui;color:#173047;max-width:1150px;margin:40px auto;padding:0 24px}table{border-collapse:collapse;font-size:12px;display:block;overflow:auto}td,th{padding:8px;border:1px solid #ccd9df;text-align:left}th{background:#e8f1f5}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f7;padding:20px}svg{width:100%;height:auto}h2{margin-top:40px}</style>' + body + '</html>'
    (OUT / 'Lab9_report.html').write_text(document)
    print('Report generated; 42 BigQuery rows verified; Firestore write/read:', smoke['write_read_equal'])


if __name__ == '__main__':
    main()
