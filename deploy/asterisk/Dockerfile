FROM debian:bullseye-slim
# NOTE: Debian's packaged Asterisk on bullseye is 16.28, which predates the
# AudioSocket() dialplan application (added in Asterisk 18.0.0). We build
# Asterisk 20 LTS from source here so AudioSocket/res_audiosocket exist.
# Single-stage build (not multi-stage): Asterisk's `make install` places
# shared libs (bundled pjproject/libasteriskssl) across several standard FHS
# paths (/usr/lib, /usr/lib/asterisk, /etc/asterisk, /var/lib/asterisk...),
# so hand-picking paths to COPY into a slim runtime stage is error-prone and
# tends to produce "missing shared library" crashes at container start.

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential wget ca-certificates pkg-config \
        libxml2-dev libsqlite3-dev uuid-dev libjansson-dev \
        libedit-dev libssl-dev libsrtp2-dev libncurses5-dev \
        libnewt-dev subversion git patch xz-utils gettext-base \
        openssl curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src
RUN wget -q https://downloads.asterisk.org/pub/telephony/asterisk/asterisk-20-current.tar.gz && \
    tar zxf asterisk-20-current.tar.gz && \
    rm asterisk-20-current.tar.gz && \
    mv asterisk-20.*/ /usr/src/asterisk

WORKDIR /usr/src/asterisk
# Bundled pjproject gives us a known-good chan_pjsip/TLS stack regardless of
# whatever (older) libpjproject may exist on the base image.
RUN ./configure --with-pjproject-bundled --with-jansson-bundled && \
    menuselect/menuselect --enable app_audiosocket --enable res_audiosocket \
        --enable res_srtp --enable chan_pjsip --enable res_pjsip \
        --enable res_pjsip_session --enable res_pjsip_outbound_registration \
        --enable codec_g711 menuselect.makeopts && \
    make -j"$(nproc)" && \
    make install && \
    make samples && \
    ldconfig

# Drop build toolchain to shrink the image; runtime shared libs (libssl,
# libsrtp2, libjansson, etc.) stay installed since they're still "depended
# on" package-wise, not dev-only headers.
RUN apt-get purge -y --auto-remove build-essential wget pkg-config \
        libxml2-dev libsqlite3-dev uuid-dev libjansson-dev libedit-dev \
        libssl-dev libsrtp2-dev libncurses5-dev libnewt-dev subversion \
        git patch xz-utils && \
    rm -rf /usr/src/asterisk /var/lib/apt/lists/*

RUN groupadd -r asterisk && useradd -r -g asterisk -d /var/lib/asterisk asterisk && \
    mkdir -p /var/log/asterisk /var/run/asterisk && \
    chown -R asterisk:asterisk /var/lib/asterisk /var/spool/asterisk \
        /var/log/asterisk /var/run/asterisk /etc/asterisk

COPY pjsip.conf.template     /etc/asterisk/pjsip.conf.template
COPY extensions.conf.template /etc/asterisk/extensions.conf.template
COPY rtp.conf.template       /etc/asterisk/rtp.conf.template
COPY entrypoint.sh           /entrypoint.sh
RUN chmod +x /entrypoint.sh

# SIP/TLS signalling + RTP media range (must match rtp.conf.template)
EXPOSE 5061/tcp
EXPOSE 10000-10200/udp

ENTRYPOINT ["/entrypoint.sh"]
