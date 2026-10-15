# Tiers A and B only. Tier C trains inside PIDSMaker; see docs/REPRODUCE.md.
FROM python:3.9-slim

# psycopg2==2.9.10 is built from source. The replay does not open Postgres;
# the library is imported only if firstalarm.db or firstalarm.freeze.db is imported.
# time: /usr/bin/time -v for the reproduction log. zstd: data/download.sh uses tar --zstd.
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libc6-dev libpq-dev time zstd curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/firstalarm
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/opt/firstalarm
# FA_ART_ROOT and FA_DATA_ROOT stay unset so data/download.sh uses ./artifacts and ./data,
# which is what docs/REPRODUCE.md tells a reader to do.
CMD ["python", "scripts/verify_numbers.py"]
