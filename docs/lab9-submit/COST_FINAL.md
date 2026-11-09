# Part 3 — фінальний стан калькуляторів

Посилання та підсумки підтверджено скриншотами/повідомленнями користувача. Agent не відкривав share estimates самостійно. CSV exports ще не додані до репозиторію. Оцінки не є рахунками або запущеними ресурсами.

| Профіль | AWS calculator, $/міс | AWS після ручної корекції пауз, $/міс | GCP calculator reference, $/міс |
|---|---:|---:|---:|
| Ніхто | 43.90 (Aurora без пауз, Lambda 0) | 0.10 | 0.00 |
| Демо | 43.90 (Aurora без пауз, Lambda 72000) | 1.30 | 0.25 |
| Office hours | 43.90 (Aurora без пауз, Lambda 633600) | 10.66 | 1.33 |
| Busy 24/7 | 44.23 | 44.23 (округлено) | 7.63 |

AWS storage: 1 GB, $0.10/month; compute 0.5 ACU × $0.12 × active hours 0/20/176/730. Ручні суми не є результатами pause-aware AWS calculator. Додаткові I/O, pause tails, backups, egress та інші exclusions поза точною моделлю. В Aurora calculator I/O задано умовним мінімумом, оскільки форма відхиляла нуль; відповідна дрібна вартість округлюється.

GCP reference має Cloud Run 0/100000/500000/2500000 requests замість точних 0/72000/633600/2628000. CPU/memory lines у наданому summary відповідають gross charges; requests line узгоджується з відніманням 2M free requests. Це висновок за breakdown, не перевірена внутрішня реалізація calculator. Firestore daily inputs застосовані протягом calculator month, а не 10/22 active days. Idle Firestore має позитивний технічний мінімум reads замість справжнього нуля; вартість залишається $0 у free quota.

Точна модель за ставками завдання: GCP Firestore core 0 / 0 / 0.0502 / 3.359 USD. Її не підмінено calculator references. Різниця через presets, активні дні та free-quota treatment, а не доказ помилкового cloud invoice.

- [AWS idle Lambda / Aurora always-on reference](https://calculator.aws/#/estimate?id=5fa89cf982739478a4723e6616dee9e52af9b1c3)
- [AWS demos reference](https://calculator.aws/#/estimate?id=e5c5452a0a0108945d39e5089680ec9bbad50e85)
- [AWS office reference](https://calculator.aws/#/estimate?id=d410722847689b0d5d41dd379b728b983f471593)
- [AWS busy](https://calculator.aws/#/estimate?id=6a2bde26c4328f535fac54c7f870d034e59485b2)
- [GCP idle reference](https://cloud.google.com/products/calculator?dl=CjhDaVEzTm1VMU9ERmhOeTAzTldJekxUUXpNRFV0WVRRMU1DMHhNVEl5TmpRME5HVXlNV01RQVE9PRAcGiRBMjMxODdFNi1BRDJCLTQwOEMtQkVGQS1GNDZENjc3MEI0NkM)
- [GCP demos approximation](https://cloud.google.com/products/calculator?dl=CjhDaVJqWkRBeU9EUTFaQzAyWW1aaExUUTVZelV0T1dKa1pTMDBOak5sTnpJd09UazFZelFRQVE9PRAXGiRBRkU0OTQ5MC1DMjkyLTQ2RkQtQkNGOC1BRDI5MUUxMzk2RjA)
- [GCP office approximation](https://cloud.google.com/products/calculator?dl=CjhDaVExTlRkaVl6azVZUzA1TkRsaExUUmhZemN0WW1Fek5TMDBZekZtWkRGaVpEQTBPR0lRQVE9PRAcGiRBMjMxODdFNi1BRDJCLTQwOEMtQkVGQS1GNDZENjc3MEI0NkM)
- [GCP busy approximation](https://cloud.google.com/products/calculator?dl=CjhDaVJoWWpObVlXRTJZUzA0TXpOaExUUmtOekF0T1daaE9TMDJaVEkyWkdFNVl6ZGpNalVRQVE9PRAXGiRBRkU0OTQ5MC1DMjkyLTQ2RkQtQkNGOC1BRDI5MUUxMzk2RjA)

Порівняння точного навантаження та висновки про дорожчу лінію наведені в ANSWERS.md. Прийнятність calculator approximations і заміни GCP deployment визначає викладач.
