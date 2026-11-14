# Reproducibility artefact: `docker build -t archlux . && docker run --rm archlux`
# regenerates every synthetic figure and checks it against results/SHA256SUMS.
# The corpus benches (B6-B9) need data that cannot be redistributed: mount it and run
# `make results-corpus` (see docs/formulas/benchmark.md, "Reproduce").
FROM python:3.12-slim

WORKDIR /archlux
COPY . .
RUN pip install --no-cache-dir -e ".[dev]"

CMD ["make", "check-results"]
