FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        asterisk \
        asterisk-modules \
        gettext-base \
        openssl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY pjsip.conf.template     /etc/asterisk/pjsip.conf.template
COPY extensions.conf.template /etc/asterisk/extensions.conf.template
COPY rtp.conf.template       /etc/asterisk/rtp.conf.template
COPY entrypoint.sh           /entrypoint.sh
RUN chmod +x /entrypoint.sh

# SIP/TLS signalling + RTP media range (must match rtp.conf.template)
EXPOSE 5061/tcp
EXPOSE 10000-10200/udp

ENTRYPOINT ["/entrypoint.sh"]
