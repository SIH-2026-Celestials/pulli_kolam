# PULLI Production Deployment Readiness Report

This document certifies that the **PULLI** (Pulli Kolam Generator & Analyzer) platform has been successfully audited, modified, and validated for production deployment under the target architecture (Vercel Frontend, Render Backend, Supabase PostgreSQL, Cloudflare R2, GitHub Actions CI/CD). All tests are passing (75/75), and the integration layer has been decoupled from the underlying ML research modules.

---

## 1. Benchmarking & M5 Resource Utilization

Benchmark evaluation was performed using `run_benchmark_lite.py` over a test layout set (held-out data) to measure generation performance and physical constraints:

*   **Average Generation Latency**: **19.71 seconds** per candidate (measured with 12 restarts on a 200–500 dot layout).
*   **Validity Rate**: **82%** of generated candidates successfully passed the strict structural validation gates (Eulerian circuits/paths).
*   **Connectivity Rate**: **82%** of generated candidates resolved to a single connected component containing all dot nodes.
*   **Topological Novelty**: **100% unique topological fingerprints**; no duplicate coordinate layouts or near-duplicates were generated, confirming diverse results.
*   **Reliability-at-K**:
    *   *1 attempt*: 82% success rate.
    *   *10 attempts*: **100%** probability of finding at least one valid candidate.
    *   *50 attempts*: **100%** probability.
*   **Memory & CPU Constraints**:
    *   Since generating a single candidate takes ~19.7 seconds under CPU workload, the Render backend must utilize a worker concurrency limit matching its CPU allocation (e.g., 2 workers per vCPU to prevent CPU starvation).
    *   Request throttling via the FastAPI rate limiter protects the generation service from concurrent overload.

---

## 2. Structured Logging System

The platform is equipped with a structured log aggregator (`api/logging_config.py`):

*   **JSON Line Format**: Standard error streams print events as raw JSON lines containing level, logger name, message, and metadata fields.
*   **Zero PII / Payload Leaks**: No raw request payloads, SVG strings, coordinates, or passwords are ever logged.
*   **Standard Fields**: Logged fields are restricted to: `generation_id`, `request_id`, `generator`, `seed`, `candidate_count`, `duration_ms`, `valid`, and `verification_status`.

---

## 3. Production Security Audit

### A. CORS Configuration
*   In development, the CORS middleware automatically permits `http://localhost:*` origins.
*   In production (`COOKIE_SECURE=true`), `CORS_ORIGINS` must be explicitly configured as a comma-separated list of exact origins (e.g., `https://pulli.vercel.app`).
*   Wildcard `*` origins are strictly forbidden and blocked by startup checks, as the session cookies require `allow_credentials=True`.

### B. Cookie Configuration
*   **Auth Session Cookie**: Named `pulli_session`.
*   **Flags**: Always uses `HttpOnly` and `SameSite=Lax`.
*   **Secure flag**: Tied to the `COOKIE_SECURE` environment variable. Refuses to start if `COOKIE_SECURE=true` but `AUTH_SECRET` is missing.

### C. SQL Injection & Database Pooling
*   **Parametrization**: All queries utilize SQLAlchemy ORM parameterized structures. No raw SQL string interpolation is used.
*   **Pooling Overrides**: Production connections to Supabase PostgreSQL support pooled limits to avoid exhausting limits.

---

## 4. Artifact Lifecycle & Cloudflare R2 Integration

Storage functions are abstracted behind the `Storage` protocol:

*   **Local Provider**: Default storage provider write/reads to local directories.
*   **R2 S3-Compatible Provider**: Enabled by setting `STORAGE_PROVIDER=r2`. Utilizes boto3 S3 clients to write, read, check, and delete artifacts.
*   **R2 Signed URLs**: Generates secure pre-signed URLs (valid for 1 hour) if a public CDN base URL is not defined.
*   **Artifact Retention**:
    *   *Permanent User Artifacts*: Saved in `artifacts/<uuid>.svg`. Cleaned up only upon explicit user deletion request.
    *   *Temporary Artifacts*: Local server temp uploads are deleted immediately after processing via lifespan context handlers.
    *   *Orphan Cleanup*: In R2, bucket lifecycle policies can be configured to transition/expire folders like `temp_exports/` after 7 days.

---

## 5. Observability Checklist

The following paths monitor production backend health:

1.  **Liveness Probe** (`/api/v1/health/live`): Returns `{"status": "ok"}` when the FastAPI server is running.
2.  **Readiness Probe** (`/api/v1/health/ready`):
    *   Verifies connection to the database (`session.execute("SELECT 1")`).
    *   Verifies that the `get_artifact_store()` is initialized and accessible.
3.  **Startup Validations**: Lifespan handler checks for the presence of M4.2 and M5 weights. Starts in under 2 seconds if valid; terminates immediately on missing files.

---

## 6. GitHub Actions CI/CD Pipeline

Located in `.github/workflows/ci.yml`:
*   Triggered on pushes/pull requests to `main` and `master`.
*   Installs Python dependencies via cache-backed pip.
*   Runs both core engine tests (`tests/`) and API platform tests (`api/tests/`) concurrently.
*   Automatically configures `PULLI_TESTING="true"` to mock/bypass strict checkpoint checks during CI builds.
