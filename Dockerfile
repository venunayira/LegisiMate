FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY misofish ./misofish
COPY web ./web
COPY scripts ./scripts
COPY data/showcase_cases.json ./data/showcase_cases.json
COPY data/open_india_law/target_legislation.parquet ./data/open_india_law/target_legislation.parquet
COPY data/open_india_law/domain_judgments.parquet ./data/open_india_law/domain_judgments.parquet
COPY data/open_india_law/extraction_manifest.json ./data/open_india_law/extraction_manifest.json

# Pre-build the SQLite + FTS5 legal corpus at image build time for <1s Cloud Run cold starts
RUN python -c "from misofish.legal import ensure_legal_db, legal_status; ensure_legal_db(); st = legal_status(); assert st['available'], st; print('Built legal_poc.db:', st)"

EXPOSE 8080

CMD ["python", "-m", "misofish.server"]
