FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY probers/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy prober source and challenges index
# index.yaml is the authoritative source for prober names and challenge metadata.
# MDX files are not needed by the runner.
COPY probers/ ./probers/
COPY challenges/index.yaml ./challenges/index.yaml

ENV PYTHONPATH=/app

CMD ["python", "-m", "probers.runner"]
