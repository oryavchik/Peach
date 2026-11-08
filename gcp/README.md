# Peach Lab 9 without a billing account

Owner instruction: do not connect any billing account, including Free Trial.
Project: peach-510910. Billing was verified disabled on 2026-11-07.

## What is actually done

- Official gcloud CLI installed locally, signed in with the owner's account.
- Official Terraform installed and downloaded provider checksums/signatures checked.
- Separate `gcp/` configuration, Google providers pinned by lockfile.
- `terraform init -backend=false` and `terraform validate` pass.
- Prepared separate `Peach-GCP` HCP workspace configuration; workspace itself
  is NOT created and no remote run is claimed.
- Prepared `bootstrap/` OIDC trust restricted by immutable HCP IDs; not applied.
- No service-account key created/downloaded.
- Actual BigQuery Sandbox query and 42 result rows exported under docs/lab9-evidence/.
- Firebase APIs enabled without billing; GET/addFirebase calls return 403
  PERMISSION_DENIED. The owner was asked to check Firebase Console Spark setup.
- Service decisions: docs/adr/0008-google-cloud-free.md.

## Safeguards

`enable_compute=false` is the default. Cloud Run, Artifact Registry, a runtime
service account and the budget resource have count=0 in that mode. No paid
billing account is created/linked by Terraform. Firebase configuration is prepared, not applied. Firestore was later created through the API (see update below). The root has no Cloud SQL, Dataflow or Vertex resource.
The optional Cloud Run resource is a future scaffold: no Firestore FastAPI
adapter/image has been authored or claimed deployed in this constrained run.

No billing means no Cloud Run deployment, even though low request traffic can
fit its free usage quota. Therefore there is no migrated frontend/API/database
URL and this lab is NOT ready to submit as fully completed. Existing AWS/Peach
production configuration and data are not changed.

## Reproduce the completed free demo

```sh
export PATH="$PWD/.local/lab9-tools/google-cloud-sdk/bin:$PATH"
export CLOUDSDK_PYTHON=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
bq --project_id=peach-510910 --location=US query \
  --use_legacy_sql=false --maximum_bytes_billed=100000000 \
  'SELECT corpus, SUM(word_count) AS total_words, COUNT(*) AS distinct_words
   FROM `bigquery-public-data.samples.shakespeare`
   GROUP BY corpus ORDER BY total_words DESC'
```

The actual job ID is peach_lab9_public_20261107_01. Table:
`peach-510910.lab9_20261107.word_counts`. Dataset default table expiry is two
days; after expiry re-run a bounded query to collect new evidence.

## Remaining browser demos

Browser host is unavailable and native Computer Use permissions are not granted, so these demos currently require browser access:

1. BigQuery Console: https://console.cloud.google.com/bigquery?project=peach-510910
   Open query history, select peach_lab9_public_20261107_01, screenshot SQL,
   result and processed bytes (3,781,873). This query actually ran.
2. Looker Studio: https://lookerstudio.google.com/ . Create a report, choose
   BigQuery connector, project peach-510910, dataset lab9_20261107, table
   word_counts. Make a bar chart with corpus and total_words, descending,
   top 10. Capture screenshot. No chart has been created by the agent.
3. Vision public OCR demo: https://cloud.google.com/vision/docs/drag-and-drop .
   Try a non-sensitive sample/receipt image and capture the Text result. This
   is a documented public demo, not a claim of a Vision API call in our project.
   If it requests billing or a CAPTCHA, do not bypass it. No OCR was run yet.

The Vision/Document AI APIs normally require billing even when usage could be
covered by free units. Gemini on Vertex and Dataflow were not run under the
no-billing constraint. They are not silently replaced with local simulations.

## Costs and cleanup

`python3 gcp/cost_model.py` produces explicit four-profile estimates, with all
assumptions and exclusions. They are not AWS/GCP calculator exports and are
not finalized Part3 evidence. At idle Cloud SQL's always-on compute is the
main trap; Firestore's trap is unbounded document reads, while Cloud Run min
instances / instance billing can remove its scale-to-zero savings.

No paid compute/database instance exists to stop. The BigQuery table expires automatically; one free-tier Firestore database and a synthetic document were later created (see update below). The dataset and enabled APIs have no
instance-based hourly charge. Delete ONLY lab9_20261107 if no longer needed;
do not delete the existing Peach project. A later Terraform destroy must
first be reviewed because this root can own a whole default Firestore DB.

## Update 2026-11-08: real free Firestore database

Firestore Standard Native `(default)` in `us-central1` was created through the
Admin API without linking billing. Google returned `freeTier: true`.
`python3 gcp/firestore_smoke.py` successfully wrote and read exactly one
synthetic document at `lab9_demo/free-tier-smoke` using a short-lived gcloud
token. Evidence: `docs/lab9-evidence/firestore-smoke.json`.
This is an authenticated Firestore REST call, not a migrated Peach FastAPI API.
No production data, public access, persistent keys, PITR or TTL were added.
Deletion protection is enabled. The one small synthetic document is retained
for review within the free quota; nothing paid was created.

Before applying this Terraform root, import the existing database into its
separate state (do not try to create it a second time):

```sh
terraform -chdir=gcp import google_firestore_database.main \
  'projects/peach-510910/databases/(default)'
```

Do this only after configuring the HCP workspace and reviewing its plan.
`deletion_policy=ABANDON` keeps this database on Terraform destroy; it is not
an instruction to delete the project or bypass deletion protection.
The rest of the Terraform root has still not been applied.

Full written answers: `docs/lab9-submit/ANSWERS.md`.
Standalone report: `docs/lab9-submit/Lab9_report.html`.
Rebuild saved-evidence report: `python3 gcp/cost_model.py` then
`python3 gcp/build_report.py`. The chart is an actual CSV visualization, not a
Looker screenshot. Browser access was tested again and remains unavailable.
Firebase addFirebase was retried and still returns 403 PERMISSION_DENIED.

## Free alternative delivery

The owner authorized explicit substitutions. The working site is
https://peach-agenda-free.peach-free-cloud-demo.workers.dev/ . It uses original
Peach frontend + Worker API + D1, not Firestore or Cloud Run. A fresh core test
passed (`python3 cloudflare/lab9-smoke.py`), retaining no synthetic item.
The report now includes offline Apple Vision OCR, a local ETL followed by a
real BigQuery batch load, and a fresh free-model agenda response. SVG replaces
Looker only for visualization. These are documented deviations from the GCP
rubric. See the final substitution table in `docs/lab9-submit/ANSWERS.md`.

The ETL table `lab9_20261107.word_shares_free_20261108` has 48h expiration.
To reproduce the load after `python3 gcp/alternatives/local_etl.py`, add the
local SDK bin to PATH, use the existing gcloud login, and run:

```sh
bq --project_id=peach-510910 --location=US load \
  --source_format=NEWLINE_DELIMITED_JSON \
  peach-510910:lab9_20261107.word_shares_free_20261108 \
  docs/lab9-evidence/etl-output.jsonl \
  corpus:STRING,total_words:INTEGER,distinct_words:INTEGER,share_of_words:FLOAT
```

For a repeat run, use a new table name (load appends by default), or wait for
expiry. Set 48h expiration for each new table and keep billing disabled.
