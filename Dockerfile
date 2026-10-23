FROM python:3.10-slim AS server

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

RUN set -eux; \
    printf '%s\n' \
        "deb https://mirrors.tuna.tsinghua.edu.cn/debian trixie main contrib non-free" \
        "deb https://mirrors.tuna.tsinghua.edu.cn/debian trixie-updates main contrib non-free" \
        "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security trixie-security main contrib non-free" \
        > /etc/apt/sources.list; \
    rm -f /etc/apt/sources.list.d/*; \
    apt-get update; \
    apt-get install -y --no-install-recommends build-essential; \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY multisource_data_agent ./multisource_data_agent
RUN python -m pip install --upgrade pip -i https://mirrors.ustc.edu.cn/pypi/simple && \
    pip install ".[deploy]" -i https://mirrors.ustc.edu.cn/pypi/simple && \
    pip check

COPY scripts/backend_entrypoint.sh ./backend_entrypoint.sh
RUN chmod +x /app/backend_entrypoint.sh && \
    sed -i 's/\r$//' /app/backend_entrypoint.sh

# Synthetic Retail data is imported explicitly by the demo bootstrap.

EXPOSE 8000
ENTRYPOINT ["./backend_entrypoint.sh"]
CMD ["uvicorn", "multisource_data_agent.main:application", "--host", "0.0.0.0", "--port", "8000"]
