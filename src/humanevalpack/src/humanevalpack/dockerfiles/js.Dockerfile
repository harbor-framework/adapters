FROM node:20.18.1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
# js-md5 is required by JavaScript/162; python3 (preinstalled) runs the verifier
RUN npm install -g js-md5@0.8.3
ENV NODE_PATH=/usr/local/lib/node_modules
WORKDIR /workspace
COPY workspace/ /workspace/
RUN mkdir -p /logs/verifier
