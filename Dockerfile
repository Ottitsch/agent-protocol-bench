FROM python:3.10-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# Expose typical ports for local testing
EXPOSE 8001 8101 8201 8301

CMD ["python", "benchmarks/run_bench.py", "--validate", "--transport", "http"]

