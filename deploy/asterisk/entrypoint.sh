#!/bin/sh
# Entrypoint for the Asterisk container: renders config templates with
# environment variables, ensures a TLS keypair exists, then starts Asterisk
# in the foreground so Docker can supervise it.
set -e

: "${SINGTEL_SIP_SERVER:?SINGTEL_SIP_SERVER is required}"
: "${SINGTEL_SIP_USERNAME:?SINGTEL_SIP_USERNAME is required}"
: "${SINGTEL_SIP_PASSWORD:?SINGTEL_SIP_PASSWORD is required}"
: "${SINGTEL_SIP_DDI:=}"
: "${AUDIOSOCKET_HOST:=app}"
: "${AUDIOSOCKET_PORT:=9092}"
: "${PUBLIC_IP:=$(curl -fsSL -4 ifconfig.co || echo 127.0.0.1)}"

echo "Rendering Asterisk config for Singtel/B3Networks trunk (${SINGTEL_SIP_SERVER})..."

export SINGTEL_SIP_SERVER SINGTEL_SIP_USERNAME SINGTEL_SIP_PASSWORD SINGTEL_SIP_DDI \
       AUDIOSOCKET_HOST AUDIOSOCKET_PORT PUBLIC_IP

envsubst '${SINGTEL_SIP_SERVER} ${SINGTEL_SIP_USERNAME} ${SINGTEL_SIP_PASSWORD} ${PUBLIC_IP}' \
    < /etc/asterisk/pjsip.conf.template > /etc/asterisk/pjsip.conf

envsubst '${SINGTEL_SIP_DDI} ${AUDIOSOCKET_HOST} ${AUDIOSOCKET_PORT}' \
    < /etc/asterisk/extensions.conf.template > /etc/asterisk/extensions.conf

cp /etc/asterisk/rtp.conf.template /etc/asterisk/rtp.conf

mkdir -p /etc/asterisk/keys
if [ ! -f /etc/asterisk/keys/asterisk.key ]; then
    echo "No TLS keypair found — generating a self-signed certificate."
    echo "Replace with a CA-signed cert for production if the carrier requires it."
    openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout /etc/asterisk/keys/asterisk.key \
        -out    /etc/asterisk/keys/asterisk.crt \
        -days 3650 \
        -subj "/CN=${PUBLIC_IP}"
fi

echo "Starting Asterisk (foreground)..."
exec asterisk -f -vvv -U asterisk -G asterisk
