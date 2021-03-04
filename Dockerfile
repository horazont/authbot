FROM debian:bullseye-slim

RUN set -eu; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update; \
    apt-get install -y --no-install-recommends python3 python3-pip python3-aioxmpp; \
    apt-get clean; \
    rm -rf /var/cache/apt/lists/*

RUN set -eu; \
    pip3 install 'environ-config~=20.1'; \
    rm -rf ~/.cache;

RUN set -eu; \
    useradd -m authbot -u 50814

USER 50814

COPY authbot /opt/authbot/authbot

WORKDIR /opt/authbot

ENTRYPOINT ["python3", "-m", "authbot"]
