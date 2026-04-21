# Scrapling to Lovable Worker

This repository now contains:

- a broad job scraper app under `job_scraper/`
- a non-invasive adapter layer under `scraper/`
- normalizes raw job payloads
- deduplicates jobs before ingestion
- batches jobs to Lovable Cloud's `ingest-scraped-jobs` backend
- can run once or as a forever worker every 5 minutes

## Current architecture

The worker now uses:

- `SCRAPER_ENTRYPOINT=job_scraper.main:scrape_all_sources`
- `JOB_SOURCE_URLS` for broad portal/source crawling
- optional `LOVABLE_SEARCH_PREFERENCES_URL` for ranking context only
- optional Google Jobs provider mode through `GOOGLE_JOBS_PROVIDER`

`python -m scraper.run_once --sample` still exists for safe ingestion verification.

## Environment variables

Required:

- `LOVABLE_INGEST_URL`
- `LOVABLE_SCRAPER_INGEST_TOKEN`
- `SCRAPER_ENTRYPOINT=job_scraper.main:scrape_all_sources`

Optional:

- `LOVABLE_SEARCH_PREFERENCES_URL`
- `SCRAPER_INTERVAL_SECONDS=300`
- `SCRAPER_BATCH_SIZE=100`
- `JOB_SOURCE_URLS=https://builtin.com/jobs/remote/dev-engineering,...`
- `GLOBAL_JOB_CATEGORIES=Software Engineering,...`
- `GLOBAL_JOB_LOCATIONS=United States,Remote,...`
- `GOOGLE_JOBS_PROVIDER=disabled|serpapi|scraperapi`
- `SERPAPI_API_KEY=...`
- `SCRAPERAPI_API_KEY=...`
- `GOOGLE_JOBS_MAX_QUERIES_PER_RUN=25`
- `GOOGLE_JOBS_MAX_RESULTS_PER_QUERY=20`
- `ENABLE_BROWSER_FETCHER=true` for optional Workday browser fallback

## Local commands

Verify Lovable ingestion with a sample payload:

```bash
python -m scraper.run_once --sample
```

Run one real scrape + ingest cycle:

```bash
python -m scraper.run_once
```

Run the scheduler worker:

```bash
python -m scraper.run_scheduler
```

If your local machine has broken proxy variables set, clear them in PowerShell before running:

```powershell
$env:HTTP_PROXY=''
$env:HTTPS_PROXY=''
$env:ALL_PROXY=''
$env:http_proxy=''
$env:https_proxy=''
$env:all_proxy=''
```

## Render

Use a Background Worker service, not a static site.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
python -m scraper.run_scheduler
```

Set environment variables:

- `LOVABLE_INGEST_URL`
- `LOVABLE_SCRAPER_INGEST_TOKEN`
- `SCRAPER_INTERVAL_SECONDS=300`
- `SCRAPER_BATCH_SIZE=100`
- `SCRAPER_ENTRYPOINT=job_scraper.main:scrape_all_sources`
- `JOB_SOURCE_URLS=...`
- `GLOBAL_JOB_CATEGORIES=...`
- `GLOBAL_JOB_LOCATIONS=...`
- `GOOGLE_JOBS_PROVIDER=disabled`

## Railway

Create a service from the repo.

Start command:

```bash
python -m scraper.run_scheduler
```

If using Docker, point Railway at `Dockerfile.scheduler`.

## Fly.io

Deploy as a worker process using `Dockerfile.scheduler` or a process command that runs:

```bash
python -m scraper.run_scheduler
```

Persist only environment variables; no secrets in source control.

## VPS

Install dependencies:

```bash
pip install -r requirements.txt
```

Run under `systemd`, `supervisord`, or `tmux`:

```bash
python -m scraper.run_scheduler
```

## Platform guidance

- Render, Railway, Fly.io, and a VPS are good fits for this always-on Python worker.
- Vercel is fine for the Lovable frontend/API side.
- Vercel is **not** a good place for this 5-minute always-running Python scheduler worker.
- Vercel cron on Hobby is not suitable for every-5-minute scraping workers.
