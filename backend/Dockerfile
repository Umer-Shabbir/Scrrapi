FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first, in their own layer: pyproject changes far less often than
# app code, so a source edit doesn't re-resolve the whole tree or re-download
# Chromium. `--no-install-project` isn't a thing for plain pip, hence the shim
# package below -- it satisfies setuptools' package discovery without copying
# the real source in yet.
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py \
    && pip install --no-cache-dir -e ".[dev]"

# Chromium + its system libs (fonts, nss, X stack). Needed by the worker; the API
# image is the same image, so it carries them too.
RUN playwright install --with-deps chromium

COPY . .

# Re-run the editable install now the real package is in place, so entry points
# and metadata match the shipped source.
RUN pip install --no-cache-dir --no-deps -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
