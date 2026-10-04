# Pinned Java 11 + Defects4J 3.0.1 + bundled Major 3.0.1 environment.
# Stock mutation only. Do not enable exportKillMap in this image.
FROM ubuntu:22.04@sha256:5ec03bb3441e8b0bf3b4f9cd4629a1ae763010dc3035bb8da3ae6cf026486401

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=America/Los_Angeles \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo "$TZ" > /etc/timezone \
    && apt-get update -y \
    && apt-get install -y --no-install-recommends \
        openjdk-11-jdk \
        git \
        subversion \
        perl \
        curl \
        wget \
        ca-certificates \
        unzip \
        zip \
        cpanminus \
        make \
        build-essential \
        time \
        python3 \
        patch \
        diffstat \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

COPY env/pin.env /opt/artifact/env/pin.env
COPY acquire/setup_defects4j.sh /opt/artifact/acquire/setup_defects4j.sh
RUN chmod +x /opt/artifact/acquire/setup_defects4j.sh \
    && PIN_ENV=/opt/artifact/env/pin.env /opt/artifact/acquire/setup_defects4j.sh /opt/defects4j \
    && rm -rf /root/.cpanm /tmp/*

ENV D4J_HOME=/opt/defects4j \
    PATH="/opt/defects4j/framework/bin:${PATH}"

COPY scripts/ /opt/artifact/scripts/
COPY tests/ /opt/artifact/tests/
RUN chmod +x /opt/artifact/acquire/setup_defects4j.sh \
        /opt/artifact/scripts/*.sh \
        /opt/artifact/tests/*.sh \
    && java -version \
    && defects4j info -p Lang >/dev/null

WORKDIR /work
CMD ["/opt/artifact/scripts/smoke_lang1.sh"]
