FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -m -s /sbin/nologin appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --no-deps -r requirements.txt

COPY download.py .
RUN chown -R 1000:1000 /app

USER 1000:1000
ENTRYPOINT ["python", "download.py"]