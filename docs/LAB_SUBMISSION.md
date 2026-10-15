# Weekly meetings report — Peach

Сайт: https://d2u4q6uy2ofop2.cloudfront.net/meetings

## Що реалізовано

EventBridge Scheduler → SQS → report-builder Lambda у VPC → PostgreSQL →
S3 через gateway endpoint → ObjectCreated → report-mailer Lambda поза VPC → SES.

CSV містить кількість і години зустрічей за вибраний ISO-тиждень, обидва
показники попереднього тижня, абсолютну зміну, розбивку за організаторами та
п’ять найдовших зустрічей із назвою, початком, тривалістю й кількістю учасників.
Межі тижня: понеділок 00:00 UTC, верхня межа не включається.

- Генератор: [weekly.py](../backend/app/reports/weekly.py).
- Builder: [lambda_handler.py](../backend/app/reports/lambda_handler.py).
- Mailer: [mailer.py](../backend/app/reports/mailer.py).
- Усі ресурси звітів: [reports.yml](../infra/reports.yml).
- Деплой: [deploy-reports.sh](../scripts/deploy-reports.sh).
- Контрольований збій і redrive: [check-report-dlq.py](../scripts/check-report-dlq.py).

Планувальник увімкнений щопонеділка о 07:00 Europe/Kyiv. Timeout builder —
60 секунд, visibility SQS — 360 секунд, BatchSize — 1, maxReceiveCount — 3.
Бакет приватний, CSV видаляються через 90 днів. Ресурси стека позначені
PROJECT_NAME=peach. Redis, RabbitMQ, Celery та RQ не розгорталися.

Відправник і отримувачі надходять із REPORT_SENDER та REPORT_RECIPIENTS.
За вибором власниці використано підтверджену Gmail-адресу замість власного
домену: власного домену немає. Це відхилення від пункту лабораторної про
reports@<domain>/DKIM. Шаблон підтримує необов’язковий SenderDomain та
виводить три пари DKIM CNAME для майбутнього власного домену.

## Матеріали для здачі

1. Посилання на коміт: буде у фінальному повідомленні; цей документ також
   входить у той самий коміт.
2. Додати справжній скриншот отриманого листа у Gmail: адресат, тема
   `Peach weekly report: 2026-W42.csv` та вкладення `2026-W42.csv`.
   Власниця вже підтвердила отримання тестового листа в чаті.
   Після оновлення CSV можна використати новий лист із розширеним звітом.
3. Вивід S3: [s3-list.txt](evidence/s3-list.txt). W41 створювався за розкладом,
   W42 — на вимогу; один ключ не може сам показати джерело, тому додаються логи.
4. Три рядки тригерів: [triggers.txt](evidence/triggers.txt).
   Історичний рядок schedule — від справжнього попереднього запуску, а не від
   ручного повідомлення з підставленим source. Поточний розклад також збережено.
5. Реальний тест DLQ/redrive: [dlq-redrive.txt](evidence/dlq-redrive.txt) та
   [dlq-errors.txt](evidence/dlq-errors.txt). Підсумок SQS:
   [dlq-move-task.json](evidence/dlq-move-task.json). Для пришвидшення тесту на порожній
   черзі visibility тимчасово дорівнював 60 секундам; збій відбувався миттєво
   перед SQL/S3. Після тесту відновлено 360 секунд і вимкнено REPORT_FAIL_WEEK.
   Початкове восьмихвилинне вікно опитування завершилося до останньої перевірки
   DLQ; наступна перевірка знайшла повідомлення після трьох реальних помилок,
   і воно було повернуте native SQS redrive. Скрипт тепер чекає до 15 хвилин.
6. Повторний запуск одного тижня: [duplicate-sends.txt](evidence/duplicate-sends.txt).
   Результат у S3 — один об’єкт W42; кожне перезаписування може надіслати лист.
7. Остаточні параметри AWS: [configuration.json](evidence/configuration.json).

Перевірити S3 самостійно:

```bash
aws s3 ls s3://peach-reports-506126098984-us-east-1/reports/ --recursive --region us-east-1
```

Ручний звіт:

```bash
make report-now WEEK=2026-W42
```

Результати: **45 backend-тестів + 19 frontend-тестів = 64 успішні тести**.
Збережений вивід: [tests.txt](evidence/tests.txt), [lint.txt](evidence/lint.txt).
Production static export із webpack, TypeScript і перевірки форматування також пройшли.

Тести: `make test` та `make lint`; генератор перевірений на локальному
PostgreSQL, SES/S3-обгортки — тестами з підставленими AWS-клієнтами.
Тести не надсилають справжніх листів. Реальні AWS-перевірки наведені вище.

## Відповіді: Part 3, Step 7

### 1. Де зберігати «цей звіт уже надіслано»?

У стійкому сховищі, наприклад DynamoDB, доступному mailer поза VPC. Ключ:
`bucket + object key + object version (або hash CSV) + recipient`.
Якщо правило продукту — лише один лист за тиждень незалежно від оновлення,
ключем буде `week + recipient`. Імена отримувачів не можна пропускати з ключа,
інакше надсилання одному користувачу заблокує інших.

Перед SES потрібен атомарний conditional write/claim із терміном lease;
після успіху — стан SENT та SES MessageId. Це стримує паралельні дублікати,
але не дає абсолютного exactly-once: якщо SES прийняв лист, а Lambda впала
до запису SENT, повтор може надіслати ще один. Запис SENT до SES створює
протилежний ризик — втрату листа. Потрібні явна політика повторів і
узгодження невизначених результатів. У лабораторній дублікати навмисно
залишені спостережуваними; SES MessageId тепер записується в CloudWatch.

### 2. Три способи доступу до SES і вартість

Оцінка для us-east-1, 730 годин/місяць, без податків, пільг, вартості SES,
обчислень, зберігання та стандартного transfer. Фактичний рахунок залежить
від кількості AZ і трафіку.

| Варіант | Постійна мережева вартість | Обробка трафіку |
|---|---:|---:|
| NAT Gateway, одна AZ | $0.045 × 730 ≈ $32.85/міс.; публічна IPv4 ще приблизно $3.65/міс. | $0.045/GB плюс можливий transfer |
| Interface endpoint SES, одна AZ | $0.01 × 730 ≈ $7.30/міс. за AZ; дві AZ ≈ $14.60 | $0.01/GB на першому тарифному рівні |
| Дві Lambda + S3 gateway endpoint | $0 постійної плати за новий NAT/PrivateLink | gateway endpoint без погодинної/GB-плати; Lambda, S3 та SES оплачуються за використання |

NAT надає вихід в інтернет; interface endpoint забезпечує приватний шлях
до SES. SES підтримує як API-, так і SMTP-endpoint: для поточного
`boto3.client("sesv2")` потрібен API-endpoint, а SMTP-endpoint вимагав би
зміни клієнта. У реалізованому split mailer не потребує доступу до БД і
залишається поза VPC.

Для додаткових 10 листів на тиждень обираю split: немає постійної мережевої
плати. При мільйоні листів також спочатку залишаю split, додаючи контроль
пропускної здатності, запити production-доступу/квот SES, обробку bounce і
дублікатів. Сам обсяг листів не робить NAT потрібним. PrivateLink обрав би
за вимогою приватного мережевого шляху; остаточний вибір перевірив би за
обсягом CSV, кількістю викликів і вимогами до ізоляції.

Джерела тарифів і можливостей, перевірені 15.10.2026:
[AWS VPC pricing](https://aws.amazon.com/vpc/pricing/),
[AWS PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/),
[SES VPC endpoints](https://docs.aws.amazon.com/ses/latest/dg/send-email-set-up-vpc-endpoints.html).
Тариф SES є окремою спільною складовою для всіх трьох варіантів:
[SES pricing](https://aws.amazon.com/ses/pricing/).

### 3. Як надіслати посилання, що працює тиждень?

Не покладатися на S3 presigned URL, підписаний короткочасними Lambda/STS
credentials: він закінчиться разом із credentials, навіть якщо ExpiresIn
дорівнює семи дням. Варіант — приватний S3 за CloudFront OAC та CloudFront
signed URL із терміном на тиждень, підписаний ключем довіреної key group.
Ключ підпису має залишатися чинним, а об’єкт — існувати весь цей час.

Інший варіант — посилання на автентифіковану сторінку Peach або непрозорий
одноцільовий токен зі строком дії сім днів: сервер перевіряє доступ і
кожного разу створює новий короткочасний S3 URL. Не потрібно створювати
довгоживучі IAM access keys лише заради посилання.

Джерела: [S3 presigned URL lifetime](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html),
[CloudFront signed URLs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-signed-urls.html).

## Повтор одного тижня

Два запити на один тиждень виконують два PutObject за тим самим ключем,
тому S3 має один поточний файл, але ObjectCreated виникає для кожного
перезаписування. Кожна подія запускає mailer і може дати окремий лист.
Idempotent file naming не означає idempotent email delivery. Також S3/SQS
можуть повторно доставити подію, тому фактичних листів може бути більше двох.
