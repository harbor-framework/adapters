FROM {image}
WORKDIR /testbed
COPY submit /usr/local/bin/submit
RUN chmod 755 /usr/local/bin/submit && git rev-parse HEAD > /usr/local/share/control-arena-base
