# Q&A Authoring Engine — Cloud Run image.
#
# Single stage on python:3.12-slim. ffmpeg provides ffprobe, which the audio probe adapter runs to
# read the duration and container of uploaded recordings (browser MediaRecorder webm/opus and
# ogg/opus, as well as wav/mp3/m4a). The app is run from source with PYTHONPATH=/app/src because
# the ASGI entrypoint `main:app` is a top-level module (src/main.py); `pip install .` only pulls
# the declared runtime dependencies. The same image runs the one-off migration job
# (`alembic upgrade head`), hence alembic.ini and migrations/ are copied in too.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml LICENSE ./
COPY src ./src
RUN pip install .

COPY alembic.ini ./
COPY migrations ./migrations

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
