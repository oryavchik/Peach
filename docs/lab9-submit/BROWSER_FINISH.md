# Пункти, що потребують браузера

Перевірено 2026-11-09: browser access host unavailable; виклик Safari через Computer Use завершився timeout. Без браузера неможливо чесно створити скриншоти калькуляторів, BigQuery, Looker та OCR-demo. Нижче — підготовлені дані, а не виконані browser demos.

## 1. BigQuery

Console: https://console.cloud.google.com/bigquery?project=peach-510910

Свіжий успішний job: `peach_lab9_public_20261109_01`, location US.
Таблиця: `peach-510910.lab9_20261107.word_counts_20261109`, 42 рядки, 48h dataset TTL.
Запит і статистика: `docs/lab9-evidence/bigquery-job-20261109.json`.
Зробити screenshot SQL + результату + bytes processed. Це має бути справжній Console screenshot, а не HTML-макет.

## 2. Looker Studio без billing

https://lookerstudio.google.com/

Важливе уточнення: офіційна документація native BigQuery connector вимагає billing project. Тому для no-billing варіанта використати File Upload → CSV зі справжнього BigQuery result:
`docs/lab9-evidence/bigquery-results-20261109.csv`.

Створити report → Add data → File Upload → CSV; corpus — Text, total_words і distinct_words — Number.
Додати bar chart: dimension corpus, metric SUM(total_words), sort total_words descending, top 10.
Назва: «Peach Lab 9 — BigQuery Shakespeare result (CSV export)».
Зберегти screenshot і URL. У підписі вказати, що джерело — CSV export BigQuery, а не live connector.
Якщо File Upload недоступний — Google Sheets із тими ж даними; це також не live BigQuery connector.
Джерело вимоги billing: https://docs.cloud.google.com/data-studio/connect-to-google-bigquery .

## 3. Pricing Calculators

AWS: https://calculator.aws/
Google: https://cloud.google.com/products/calculator

Калькулятори не створюють cloud resources. Не запускати «Deploy», «Start trial» або підключення billing.
Зберегти окремий estimate для кожного профілю; врахувати, чи calculator включає free quotas. Не називати власний Python CSV calculator export.

| Профіль | Active h | Active days | Requests/month | Firestore reads/day | Writes/day |
|---|---:|---:|---:|---:|---:|
| Ніхто | 0 | 0 | 0 | 0 | 0 |
| Демо | 20 | 10 | 72000 | 14400 | 360 |
| Office | 176 | 22 | 633600 | 57600 | 1440 |
| 24/7 | 730 | 30.4167 | 2628000 | 172800 | 4320 |

AWS us-east-1: Lambda x86, 512 MB, 100 ms; Aurora PostgreSQL Serverless v2 — 0.5 ACU в active hours, 1 GB storage. Для pause savings, якщо calculator не підтримує pause, окремо додати арифметику active hours і явно відмітити її як ручну корекцію. I/O та frontend transfer не вигадувати: unknown/excluded.
GCP us-central1: Cloud Run request-based 1 vCPU, 512 MiB, 100 ms, min 0; Cloud SQL db-f1-micro 10 GB SSD 730h або active hours при scheduled stop; Firestore Standard Native 0.1 GiB, reads/writes із таблиці.
Для нульового frontend/CDN припускаємо, що storage й transfer у free quota; це не обіцянка необмеженого безкоштовного CDN. Квоти shared і мають бути доступні акаунту.

## 4. Firebase

https://console.firebase.google.com/

Перевірити акаунт і «Add Firebase to existing Google Cloud project» → peach-510910, Spark, без billing/Analytics якщо Analytics не потрібна.
403 може означати IAM permissions або Firebase Terms; це вказано в офіційній документації. Прийняття Terms — юридична дія, користувач має переглянути її та підтвердити окремо. Billing не є запропонованим вирішенням 403.
Не змінювати Firestore security rules на public. Не деплоїти поточний frontend на Firebase без адаптації API/auth: він використовує same-origin Cloudflare API та host cookie; простий static upload не створить робочий GCP core.
Джерело: https://firebase.google.com/docs/projects/use-firebase-with-existing-cloud-project .

## 5. Google OCR public demo

https://docs.cloud.google.com/vision/docs/drag-and-drop

Завантажити `docs/lab9-evidence/synthetic-receipt.png` (синтетичний чек, не персональні дані).
Відкрити text/JSON result, зберегти screenshot. Якщо виникне CAPTCHA/Terms — потрібна участь користувача; billing не підключати. Без реального результату не позначати виконаним. Це public demo, не project-scoped Vision API deployment.

## GitHub уже виконано

Гілка: https://github.com/oryavchik/Peach/tree/lab9-free-substitutions
Основний commit: https://github.com/oryavchik/Peach/commit/0dea3843
GCP Terraform/ADR commit: https://github.com/oryavchik/Peach/commit/41fa5a17
