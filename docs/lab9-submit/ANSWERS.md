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

Немає deployed GCP core URL, застосованого HCP Terraform workspace, provider calculator exports, Looker/OCR screenshots, Vertex/Dataflow runs. Без billing немає Cloud Run; Firebase повертає 403. Доступ до браузера зараз недоступний. Локальні результати та конфігурацію не видаємо за хмарний деплой.

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
