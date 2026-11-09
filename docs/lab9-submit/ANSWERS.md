# Lab 9 — Google Cloud: відповіді та межі виконання

Дата перевірки: 2026-11-08. Проєкт: `peach-510910`.

## Part 0–2: рішення

Вибір сервісів і компроміси: [ADR](../adr/0008-google-cloud-free.md).
Terraform має окремий root/state, власну runtime identity та підготовлений HCP OIDC.
`validate` не означає `apply`. Cloud Run scaffold не є готовим Firestore-бекендом.
Firebase GET/addFirebase повторно перевірено: 403 PERMISSION_DENIED. Список доступних Firebase-проєктів порожній.
Billing повторно перевірено: вимкнено. Платні сервіси та trial не активували.

Cloud SQL зберігає SQLAlchemy, joins і міграції. Постійний режим — $9.365/міс лише compute+10 GB SSD за ставками завдання. Зупинка залишає $1.70 storage і робить API недоступним. Firestore прибирає idle compute, але потребує документної моделі, перевірки власника й переписування SQL-запитів. Доступ напряму з браузера можливий із Firebase Auth та строгими security rules; це інша архітектура, а не Cloud Run/FastAPI з завдання. Зберігати Aurora в AWS простіше, але це залишає затримку, egress і не виконує вимогу перенесення БД.

Email, авторизація Cognito, weekly report та agenda parser залишаються в AWS. Новий email API key не створено: використовується наявна SES IAM identity. При майбутньому сторонньому email-провайдері ключ зберігати в Secret Manager, не у frontend або репозиторії.

## Part 3: вартість

[Чотири профілі](../lab9-evidence/cost-profiles.csv), [припущення](../lab9-evidence/cost-assumptions.json), генератор `python3 gcp/cost_model.py`.
Це модель за ставками завдання, не експорт калькуляторів і не фактичний рахунок.
1 request/s під час активності, 100 ms active CPU на запит, 512 MiB, 2 document reads/request і 5% write requests. Cloud Run рахується без перекриття CPU-інтервалів; concurrency може змінити оцінку. Вільні квоти вважаємо невикористаними іншими workloads. Для AWS право на free tier потрібно перевірити для конкретного акаунта. Aurora — ідеалізоване миттєве pause без tail; це нижня межа.

| Профіль | AWS Aurora core | GCP Firestore core | GCP Cloud SQL always-on core | Дешевше в моделі |
|---|---:|---:|---:|---|
| Ніхто | $0.1000 | $0 | $9.3650 | Firestore; storage/compute БД |
| Демо 20 год | $1.3000 | $0 | $9.3650 | Firestore; active Aurora compute |
| Робочі години 176 год | $10.6600 | $0.0502 | $9.3650 | Firestore; active Aurora compute |
| 24/7, 730 год | $44.2256 | $3.3590 | $11.6034 | Firestore; active Aurora compute |

Cloud SQL проти Aurora: AWS дешевше для idle/демо; GCP дешевше для office/24h у цій моделі. Рішення змінює одна лінія — compute БД. Firestore виграє ціною переписування коду.

Пастки GCP: Cloud SQL не засинає від відсутності запитів; зупинена БД зберігає storage charges. Cloud Run min instances, instance-based billing, велика тривалість/пам’ять і polling збільшують ціну. Firestore listeners, повторні list/aggregate, index reads та offset-pagination збільшують read operations. Денна квота не переноситься між днями.

До калькуляторів переносити для кожного профілю: requests 0 / 72000 / 633600 / 2628000; Lambda 512 MB, 100 ms; Cloud Run 1 vCPU, 512 MiB, 100 ms; Firestore reads 2×requests і writes 0.05×requests, окремо по активних днях; Aurora 0.5 ACU × 0/20/176/730 год +1 GB storage; Cloud SQL db-f1-micro 730 год +10 GB SSD (або 0/20/176/730 год для scheduled stop). Frontend transfer/storage задавати за вимірюваннями, а не прирівнювати будь-який трафік до $0. У поточній моделі frontend, registry/secrets/logging вміщуються у вільні квоти; egress, I/O та backups поза моделлю.

## Part 4: BigQuery і BI

Виконаний запит:

```sql
SELECT corpus, SUM(word_count) AS total_words, COUNT(*) AS distinct_words
FROM `bigquery-public-data.samples.shakespeare`
GROUP BY corpus ORDER BY total_words DESC;
```

Job `peach_lab9_public_20261107_01`, location US, 42 рядки, 3 781 873 bytes processed, maximumBytesBilled=100000000. CSV/JSON і job metadata збережені у `docs/lab9-evidence/`. Таблиця має строк життя 48 годин; після цього використовувати CSV або повторити обмежений запит. Локальний графік у HTML побудований із реального CSV. Він не є виконаним Looker Studio demo.

Для Looker: BigQuery connector → peach-510910 → lab9_20261107 → word_counts; dimension corpus, metric total_words, sort descending, top 10. Після expiry таблиці можна імпортувати збережений CSV у Looker як File Upload. Скриншот має показувати справжній графік Looker.

## Document AI чи general LLM

Document AI кращий для повторюваної обробки рахунків/форм, таблиць, координат тексту, confidence і стабільної структури. OCR дістає текст, але сам по собі не визначає домовленості та відповідальних на зустрічі. Gemini кращий для семантики agenda, узагальнення й неоднозначних формулювань; необхідні schema validation, підтвердження людиною і заборона вигаданих дат/імен. Практичний ланцюжок: OCR → validated text → LLM → JSON schema → user approval. OCR confidence не гарантує правильності LLM-висновку.

Vision/Document AI не запускали: немає billing. Безкоштовний локальний OCR технічно можливий, але не підтверджує демо сервісу Google. Публічний Vision demo можна використати лише якщо він доступний без billing; результат треба зафіксувати реально. Gemini в AI Studio є окремим продуктом і не підтверджує запуск Vertex AI Studio.

## Відповідність payments pipeline

S3 raw → Cloud Storage; Glue ETL → Dataflow/Apache Beam; Athena SQL → BigQuery SQL; QuickSight → Looker Studio. Glue catalog/external tables/partition discovery частково замінюються керованими BigQuery tables і load jobs. BigQuery сам керує SQL compute, масштабуванням і columnar storage; це не скасовує dedup, schema contracts, partitioning/clustering, lifecycle та IAM. Dataflow керує workers, autoscaling, checkpoints і retries, але windowing, late events, idempotency й dead-letter обробку потрібно спроєктувати.

Dataflow Text to BigQuery — batch import з GCS із JSON schema та JavaScript UDF у BigQuery table. Для одного маленького файлу без трансформацій безкоштовніший і простіший bounded BigQuery load job або локальна підготовка CSV. Це не заміняє виконання саме Dataflow template з умови. Dataflow job не створювали, бо потрібен billing.

## Part 5: сертифікації

Найближча до Parts 0–2 — Associate Cloud Engineer; до BigQuery/Dataflow/Looker — Associate Data Practitioner. Сертифікація систематизує знання, але не замінює робочий деплой. Іспит не потрібний для базової здачі лабораторної; для бонусу узгодити перелік із викладачем. Платний іспит не бронювали.

## Що ще об’єктивно не виконано

Немає deployed GCP core URL, застосованого HCP Terraform workspace, provider calculator exports, Google OCR screenshots, Vertex/Dataflow runs. Без billing немає Cloud Run; Firebase повертає 403. Доступ до браузера зараз недоступний. Локальні результати та конфігурацію не видаємо за хмарний деплой.

## Очищення

Cloud SQL/Run/Dataflow не створено — немає instance compute для зупинки. BigQuery table має 48h expiry, exports лишаються в репозиторії. Firestore Native Standard `(default)` реально створена без billing (`freeTier: true`), deletion protection увімкнено. Один синтетичний документ `lab9_demo/free-tier-smoke` записано і прочитано через authenticated REST; див. `firestore-smoke.json`. Персональні дані не переносили. Це не migrated FastAPI endpoint. Документ залишено для перевірки у free quota; TTL/PITR не вмикали. Наявний Peach project не видаляти. `terraform destroy` не виконувати над чужими ресурсами. Звіряти фактичний status/evidence перед наступним apply.

## Офіційні джерела

- https://firebase.google.com/docs/projects/billing/firebase-pricing-plans
- https://cloud.google.com/firestore/pricing
- https://docs.cloud.google.com/vision/docs/setup
- https://docs.cloud.google.com/pubsub/docs/stream-messages-dataflow
- https://cloud.google.com/run/pricing
- https://cloud.google.com/sql/pricing
- https://aws.amazon.com/lambda/pricing/
- https://aws.amazon.com/rds/aurora/pricing/

## Безкоштовні заміни, виконані за рішенням власника 2026-11-08

Це альтернативне виконання. Відповідність вимогам конкретних GCP-сервісів оцінює викладач. Платні підписки не підключали. Наявний Cloudflare deployment використано повторно, замість створення дубля.

| Вимога | Фактично виконана заміна | Чим відрізняється |
|---|---|---|
| Firebase Hosting | Cloudflare Workers Static Assets, оригінальний Next.js export | Інший провайдер; HTTPS і статичний frontend працюють |
| Cloud Run FastAPI | Cloudflare Workers, JavaScript API сумісне з інтерфейсом Peach | Не Docker/FastAPI; інше runtime та CPU/request limits |
| Cloud SQL | Cloudflare D1, наявні SQL migrations та owner-scoped prepared statements | SQLite, не PostgreSQL; історичні AWS-дані не переносили |
| GCP database demo | Firestore free-tier REST write/read | Реальний GCP; окремий smoke test, не база Cloudflare-застосунку |
| Looker Studio chart | Реальний Data Studio report над CSV із BigQuery, створений користувачем | Native BigQuery connector замінено CSV File Upload; графік підтверджено скриншотом |
| Vision/Document AI OCR | Apple Vision VNRecognizeTextRequest на синтетичному чеку | Локальний OCR без мережі, не Google OCR; не показує Form Parser |
| Dataflow Text → BigQuery | Python CSV → typed JSONL → справжній BigQuery batch load | Немає Beam workers, GCS input, autoscaling чи managed streaming |
| Vertex AI agenda prompt | Наявний Worker → OpenRouter :free model | Не Gemini/Vertex; результат конкретного запуску та статус у free-agenda-demo.json |
| Cognito sign-in | Наявна demo-сесія одного власника | HttpOnly Secure signed cookie, не багатокористувацька IAM система |

### Перевірений застосунок

URL: https://peach-agenda-free.peach-free-cloud-demo.workers.dev/
Вхід: локальний `.env`, поле `CLOUDFLARE_DEMO_PASSWORD`. Пароль у звіт не копіюється.
Перевірка `python3 cloudflare/lab9-smoke.py`: frontend /home, /items, /meetings — HTTP 200; unsigned /api/v1/items — 401; після входу SELECT 1 health ready підтвердив D1; синтетичну задачу створено, знайдено повторним list-запитом і видалено. Відповіді з особистими записами не експортовано. Доказ: cloudflare-core-check.json.

Firestore не приєднували до Worker через довготривалий Google ключ або відкриті security rules. Залишили робочу D1 інтеграцію. Google Firestore demo окреме; у звіті немає твердження, що сайт читає Firestore.

### OCR

Вхід — згенерований чек, не реальна покупка. Локальний Apple Vision розпізнав заголовки, дату, товари й total 8.00; confidence для кількості/ціни нижчий (приблизно 0.3), порядок колонок відрізняється від reading order. OCR текст не можна без перевірки вважати структурованим рахунком. Джерело/результат: synthetic-receipt.png, ocr-expected.txt, local-ocr.json.
Відтворення на macOS: `python3 gcp/alternatives/make_receipt.py`, потім `swift -module-cache-path .local/lab9-swift-cache gcp/alternatives/ocr.swift docs/lab9-evidence/synthetic-receipt.png`.

### ETL і BigQuery

`python3 gcp/alternatives/local_etl.py`: 42 реальні публічні BigQuery result rows → цілі типи + share_of_words → JSONL. Перевірено унікальність corpus і суму часток 1. JSONL завантажено у реальну таблицю `peach-510910.lab9_20261107.word_shares_free_20261108`. Load job і verification JSON збережені, TTL таблиці 48 годин. Для перевірки задано maximumBytesBilled=10485760 (10 MiB); попередній нижчий ліміт 10000000 був відхилений. BigQuery sandbox лишився без billing.

### Вартість альтернативи

Для навчального використання очікувана додаткова вартість цих замін — $0 у вільних квотах, без нових платних підписок. Cloudflare Free: 100000 Worker requests/day, D1 5 млн rows read/day, 100000 rows written/day; також діють CPU, storage та інші обмеження. При 1 request/s цілий день — 86400 API requests/day; 2 indexed row reads/request — 172800 rows/day; 5% writes — 4320/day плюс index maintenance. Це workload assumption, не вимірювання фактичних scans чи CPU. Неефективний SQL може сканувати значно більше рядків. Перевищення квот Free означає недоступність/помилки, а не обіцянку необмеженого $0. Сам Cloudflare тариф через billing API не підтверджено: раніше token отримував 403; upgrade не виконували. Наявні AWS-ресурси мають окремі витрати й цією заміною не зупинені.

Офіційні квоти: https://developers.cloudflare.com/workers/platform/limits/ і https://developers.cloudflare.com/d1/platform/pricing/ .

### Межі цієї здачі

Функціональні заміни не перетворюють Cloudflare на GCP. GCP Terraform apply/HCP workspace, Cloud Run, Firebase Hosting, Vertex, Dataflow та Google OCR screenshots не виконані. Таблиця вище прямо документує всі відхилення. Для буквального виконання вимог потрібні інші дозволи/доступи або погодження замін викладачем.

### Якість безкоштовної agenda-моделі

Свіжий запит повернув HTTP 200 та cost_usd=0, але `10:00 Kyiv time` для 19 жовтня 2026 модель перетворила на `10:00+00:00`. За zoneinfo Europe/Kyiv правильний offset цієї дати +03:00 (07:00 UTC). Отже структурна валідація JSON успішна, семантика часу — ні. Це демонструє потребу перевірки людиною; відповідь не зберігали до зустрічі. Не заявляємо повної точності чи еквівалентної якості Vertex/Gemini.

## Оновлення 2026-11-09

Код опубліковано: https://github.com/oryavchik/Peach/tree/lab9-free-substitutions . Terraform/ADR commit: https://github.com/oryavchik/Peach/commit/41fa5a17 .

BigQuery public query повторно успішно виконано: job peach_lab9_public_20261109_01, 42 рядки, 3 781 873 bytes processed. Таблиця word_counts_20261109 expires 2026-11-11T11:25:00.492000+02:00. Свіжий CSV збережено.

Виправлення попередньої поради: native BigQuery connector у Looker Studio вимагає billing project за офіційною документацією. Без billing використовувати File Upload з CSV результату або Google Sheets. Джерело: https://docs.cloud.google.com/data-studio/connect-to-google-bigquery .

Firebase знову 403; project Owner role підтверджено. Неприйняті Firebase Terms — можлива причина, а не доведений діагноз. Браузер повторно недоступний, тому calculator exports і public OCR не виконані. Data Studio chart користувач пізніше створив вручну (див. нижче). Підготовлено BROWSER_FINISH.md із даними для завершення.

## Data Studio — виконано користувачем

Звіт: https://datastudio.google.com/u/0/reporting/77dec92a-ecdc-48a6-ae33-da3e0c3699e7/page/IBBDG

На наданих скриншотах підтверджено top-10 corpus за SUM(total_words), descending, без Others. Джерело — CSV File Upload файлу bigquery-results-20261109.csv зі справжнього BigQuery result. Назва: Peach Lab 9 — BigQuery results. Це реальний графік у Data Studio, а не локальна заміна. Native BigQuery connector не використовувався. Посилання збережено без перевірки sharing permissions; користувачеві потрібно перевірити доступ викладача. Скриншот у чаті наявний, окремий image file у repository ще не додано.
