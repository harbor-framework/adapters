FROM python:3.13-slim-bookworm
WORKDIR /app
COPY lookup.py native_lookups.py inventory.json AGENTDOJO-LICENSE /opt/travel/
RUN chmod 755 /opt/travel/lookup.py && ln -s /opt/travel/lookup.py /usr/local/bin/travel-lookup
