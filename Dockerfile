# PULLI API runtime image -- api/main.py (FastAPI) only.
#
# Scope, per docs/DEPLOYMENT_AUDIT.md and the project's deployment
# invariants:
#   - CPU-only. No CUDA. torch is installed from PyPI's dedicated CPU
#     wheel index so no nvidia-* GPU packages are pulled in.
#   - No compiler toolchain: numpy/scipy/opencv/torch all ship
#     prebuilt manylinux wheels for this Python/arch combination.
#   - Only the runtime-required subset of experiments/m4_1 and
#     experiments/m4_2 is copied in -- their model-definition modules
#     (imported live by api/detectors.py and api/main.py's
#     /api/v1/model endpoint), NOT their training data or notebooks.
#     experiments/m4_1/results/dot_heatmap_net.pt is intentionally NOT
#     copied: it is not imported or referenced anywhere in api/ (only
#     experiments/m4_2/results/dot_heatmap_net_v2.pt is loaded by the
#     ML detector) -- verified by grep across api/ and
#     experiments/m4_2/*.py before writing this file.
#   - engine/ml_contract.py, engine/image_io.py's trace_path(), and the
#     rest of engine/ are copied unmodified -- this build step does not
#     alter any research code.

FROM python:3.11-slim

WORKDIR /app

# Install CPU-only torch from its dedicated index first (avoids pulling
# CUDA wheels + nvidia-* dependency packages that `pip install torch`
# installs by default on Linux), then the rest of the API's pinned
# dependency set.
COPY requirements-engine.txt requirements-ml.txt requirements-api.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.11.0 \
    && pip install --no-cache-dir -r requirements-api.txt

# Runtime source -- engine/ (deterministic research engine, unmodified)
# and api/ (FastAPI service) in full; both are small pure-Python trees.
COPY engine/ ./engine/
COPY api/ ./api/

# Only the runtime-required pieces of experiments/: package markers,
# the model-definition modules imported by api/detectors.py and
# api/main.py, and the one checkpoint the ML detector actually loads.
# experiments/*/data, tests/, train.py, evaluate*.py, and the m4.1
# checkpoint are deliberately excluded (see header comment above).
COPY experiments/__init__.py ./experiments/__init__.py
COPY experiments/m4_1/__init__.py ./experiments/m4_1/__init__.py
COPY experiments/m4_1/peak_detect.py ./experiments/m4_1/peak_detect.py
COPY experiments/m4_2/__init__.py ./experiments/m4_2/__init__.py
COPY experiments/m4_2/model.py ./experiments/m4_2/model.py
COPY experiments/m4_2/ml_lattice_detector.py ./experiments/m4_2/ml_lattice_detector.py
COPY experiments/m4_2/gated_ml_lattice_detector.py ./experiments/m4_2/gated_ml_lattice_detector.py
COPY experiments/m4_2/results/dot_heatmap_net_v2.pt ./experiments/m4_2/results/dot_heatmap_net_v2.pt

# Only the runtime-required pieces of experiments/m5_generation:
COPY experiments/m5_generation/checkpoints/placement_scorer.pt ./experiments/m5_generation/checkpoints/placement_scorer.pt
COPY experiments/m5_generation/data/split_manifest.json ./experiments/m5_generation/data/split_manifest.json

# Seed data and migrations
COPY alembic.ini ./alembic.ini
COPY alembic/ ./alembic/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health', timeout=3)" || exit 1

# Production mode -- no --reload. KMP_DUPLICATE_LIB_OK is set inside
# api/main.py itself (see its module docstring); not repeated here.
# Bind dynamically to Render/Fly.io platform PORT environment variable.
# Run migrations automatically on container startup.
CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
