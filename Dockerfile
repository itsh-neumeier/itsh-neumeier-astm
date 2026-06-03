FROM debian:bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    BACKUP_DIR=/backups \
    ASTERISK_ETC=/etc/asterisk \
    WEB_PORT=8080

ARG ASTERISK_URL=https://downloads.asterisk.org/pub/telephony/asterisk/asterisk-20-current.tar.gz

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates curl tini python3 python3-pip python3-venv \
       build-essential bison flex file pkg-config tar xz-utils \
       libedit-dev libssl-dev libxml2-dev libsqlite3-dev uuid-dev \
       libncurses-dev libcurl4-openssl-dev libspeexdsp-dev libogg-dev \
       libvorbis-dev libopus-dev libresample1-dev libsrtp2-dev \
    && mkdir -p /usr/src/asterisk \
    && curl -fsSL "$ASTERISK_URL" | tar -xz --strip-components=1 -C /usr/src/asterisk \
    && cd /usr/src/asterisk \
    && ./configure --with-pjproject-bundled --with-jansson-bundled \
    && make menuselect.makeopts \
    && make -j"$(nproc)" \
    && make install \
    && make samples \
    && cp -a /etc/asterisk /opt/asterisk-defaults \
    && cd / \
    && rm -rf /usr/src/asterisk \
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
