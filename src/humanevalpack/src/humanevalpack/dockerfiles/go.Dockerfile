FROM golang:1.22.12-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
# Pre-fetch testify (used by every upstream Go test) and warm the build cache so
# tests also run offline.
RUN mkdir -p /opt/humanevalpack/go && cd /opt/humanevalpack/go \
    && go mod init humanevalpack \
    && go get github.com/stretchr/testify/assert@v1.9.0 \
    && printf 'package main\n\nimport (\n    "testing"\n    "github.com/stretchr/testify/assert"\n)\n\nfunc TestWarm(t *testing.T) { assert.Equal(t, 1, 1) }\n' > warm_test.go \
    && go test warm_test.go && rm warm_test.go
WORKDIR /workspace
RUN cp /opt/humanevalpack/go/go.mod /opt/humanevalpack/go/go.sum /workspace/
COPY workspace/ /workspace/
RUN mkdir -p /logs/verifier
