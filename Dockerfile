# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# AI-Powered Customer Complaint & Case Processing System — container image
#
# This is a BATCH job image, not a web server: the container runs main.py
# once, processes every file in /app/data, writes results to /app/output,
# then exits. In Azure this is deployed as an Azure Container Instance (ACI)
# with an Azure File Share mounted at /app/data and /app/output so files
# persist between runs (see docs/AZURE_DEPLOYMENT.md).
# ---------------------------------------------------------------------------

FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr —
# we want logs to stream immediately for `az container logs`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install OS packages required by PyMuPDF (fitz) at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# --trusted-host works around SSL certificate verification failures caused by
# corporate network TLS-inspection proxies (common on managed work laptops).
# Remove these flags once building on a network without such a proxy.
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY . .

# These directories are overlaid by the mounted Azure File Share at runtime;
# creating them here keeps local `docker run` usable without a mount too.
RUN mkdir -p /app/data /app/output /app/logs

# No EXPOSE/ports — this is a run-to-completion job, not a web service.
ENTRYPOINT ["python", "main.py"]
