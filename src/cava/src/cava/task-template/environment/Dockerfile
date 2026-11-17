FROM python:3.12-slim

WORKDIR /app

COPY task.json functions.json /app/
COPY call_function /usr/local/bin/call_function
RUN chmod 755 /usr/local/bin/call_function
