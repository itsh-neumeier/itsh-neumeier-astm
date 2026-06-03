FROM ubuntu:24.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    BACKUP_DIR=/backups \
    ASTERISK_ETC=/etc/asterisk \
    WEB_PORT=8080

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       asterisk ca-certificates python3 python3-pip python3-venv tini \
    && cp -a /etc/asterisk /opt/asterisk-defaults \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/itsh-neumeier-astm
COPY requirements.txt .
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

VOLUME ["/data", "/backups", "/etc/asterisk"]
EXPOSE 8080/tcp 5060/udp 10000-20000/udp

ENV PATH="/opt/venv/bin:${PATH}"
ENTRYPOINT ["/usr/bin/tini", "--", "./entrypoint.sh"]
