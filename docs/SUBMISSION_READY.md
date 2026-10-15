# Weekly meetings report — Peach

## 1. Коміт

[Коміт із реалізацією звіту, CloudFormation-шаблоном і двома Lambda handlers](https://github.com/oryavchik/Peach/commit/a9965120d45c7702a001cab05b5783047fc0e31c).

Архітектура: EventBridge Scheduler → SQS → builder Lambda у VPC → PostgreSQL → S3 → mailer Lambda поза VPC → SES.
Використано підтверджену SES Gmail-адресу, без власного домену.

## 2. Скриншот листа

**Додати справжній скриншот із Gmail:** отриманий лист із темою
`Peach weekly report: 2026-W42.csv` та видимим вкладенням `2026-W42.csv`.
Отримання тестового листа вже підтверджено власницею скриньки.

## 3. Звіти у S3

Команда:

```bash
aws s3 ls s3://peach-reports-506126098984-us-east-1/reports/ --recursive --region us-east-1
```

Збережений фактичний вивід:

```text
2026-10-15 13:55:06        195 reports/2026-W39.csv
2026-10-14 23:19:38        195 reports/2026-W40.csv
2026-10-14 21:49:56        195 reports/2026-W41.csv
2026-10-15 15:52:16        505 reports/2026-W42.csv
```

`2026-W41` створювався за розкладом, `2026-W42` — на вимогу через
`make report-now WEEK=2026-W42`. Джерела підтверджуються логами нижче.

## 4. Три рядки CloudWatch

Фактичні рядки із груп `/aws/lambda/peach-report-builder` і
`/aws/lambda/peach-report-mailer`. Час у логах — UTC; рядок schedule
збережено з попереднього запуску планувальника.

```text
2026-10-14T18:49:55 [INFO]	2026-10-14T18:49:55.238Z	d2a8ad71-d2aa-54cd-bb4c-ce3803a3b1cb	trigger=schedule week=2026-W41
[INFO]	2026-10-15T12:52:14.268Z	71781069-2e97-5503-9672-7323e02fe554	trigger=sqs week=2026-W42
[INFO]	2026-10-15T12:52:18.503Z	83f82f46-f2c4-4672-8d78-aecb75af4036	trigger=s3 bucket=peach-reports-506126098984-us-east-1 key=reports/2026-W42.csv
```

## 5. Короткі відповіді: Part 3, Step 7

**Де зберігати «звіт уже надіслано» та яким буде ключ?**

У DynamoDB: ключ `bucket + object key + versionId (або hash CSV) + recipient`.
Перед надсиланням — атомарне захоплення запису зі станом PROCESSING і lease,
після прийняття SES — SENT та MessageId. Якщо потрібен лише один лист на
тиждень незалежно від змін CSV, ключ — `week + recipient`. Залишається вікно
між прийняттям SES і записом SENT: збій у ньому може дати дублікат, тому така
схема сама по собі не гарантує exactly-once.

**Три способи доступу до SES і щомісячна вартість. Що обрати для 10 листів
на тиждень та для мільйона?**

Оцінка для us-east-1, 730 годин на місяць. Це мережева складова; SES,
Lambda, S3, податки та можливий data transfer оплачуються окремо.

| Варіант | Орієнтовна мережева вартість |
|---|---|
| NAT Gateway, одна AZ | $32.85/міс. + приблизно $3.65 за public IPv4 + $0.045/GB |
| SES interface endpoint, одна AZ | $7.30/міс. за AZ + $0.01/GB на першому тарифному рівні |
| Builder у VPC, mailer поза VPC, S3 gateway endpoint | $0 постійної плати за NAT/PrivateLink; оплата Lambda/S3/SES за використання |

Для додаткових 10 листів на тиждень обираю split, реалізований у цій роботі.
Для мільйона також починаю зі split, додаючи контроль швидкості, production
доступ і квоти SES, обробку bounce та дублікатів. Великий обсяг сам по собі
не вимагає NAT. Interface endpoint обрав би за вимогою приватного шляху до
SES; NAT — коли потрібен також вихід до інших інтернет-сервісів.
Для поточного boto3 SESv2 потрібен API endpoint; SMTP endpoint потребує SMTP-клієнта.

Джерела цін і можливостей, перевірені 15.10.2026:
[AWS VPC](https://aws.amazon.com/vpc/pricing/),
[AWS PrivateLink](https://aws.amazon.com/privatelink/pricing/),
[SES VPC endpoints](https://docs.aws.amazon.com/ses/latest/dg/send-email-set-up-vpc-endpoints.html).

**Як зробити посилання, що працює тиждень?**

Використати CloudFront signed URL із терміном сім днів до приватного S3
через OAC, підписаний ключем довіреної key group. Він не залежить від строку
життя тимчасових credentials Lambda; ключ і об’єкт мають залишатися чинними.
Інший варіант — посилання на захищену сторінку Peach із токеном на сім днів,
яка після перевірки доступу щоразу видає свіжий короткочасний S3 presigned URL.
Просто збільшити ExpiresIn для Lambda-signed URL недостатньо.
Джерела: [S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html),
[CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-signed-urls.html).

## Додаткова перевірка

45 backend-тестів і 19 frontend-тестів пройшли. Реально перевірено три
невдалі спроби → DLQ → redrive → успішну генерацію й прийняття листа SES.
Повторні команди створили один поточний файл W42 у S3 та два різні SES
MessageId. Повні докази: [LAB_SUBMISSION.md](LAB_SUBMISSION.md).
