FROM vllm/vllm-openai-cpu:latest

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/vllmuser \
    PYTHONPATH=/app \
    VLLM_LOGGING_CONFIG_PATH=/app/logging_config.json \
    VLLM_TARGET_DEVICE=cpu

WORKDIR /app

RUN groupadd -g 1000 vllmuser && \
    useradd -r -u 1000 -g vllmuser -m -d /home/vllmuser -s /sbin/nologin vllmuser

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --no-deps -r /app/requirements.txt

COPY log_filter.py /app/log_filter.py
COPY logging_config.json /app/logging_config.json

RUN chown -R 1000:1000 /app /home/vllmuser

USER 1000:1000

EXPOSE 8000
ENTRYPOINT ["vllm", "serve"]