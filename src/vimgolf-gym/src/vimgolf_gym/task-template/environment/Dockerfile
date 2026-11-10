# Agent sandbox: the published upstream VimGolf verifier image (python:3.11-slim/trixie,
# vim, vimgolf==0.5.1), so local `vimgolf local` checks use the same Vim as the grader.
FROM agile4im/vimgolf-verifier:v0.0.3@sha256:be597cfda162160ab3f6be0ce5897314957845bfbb758a884ddc721b5046c8da
# The image's ENTRYPOINT is ["sh"], which would turn Harbor's `sh -c "sleep infinity"`
# into `sh sh -c ...` (exit 2); clear it.
ENTRYPOINT []

WORKDIR /app

COPY input.txt output.txt challenge.json /app/
# The image's verifier script embeds a demo challenge with its solution; the agent
# sandbox does not need it (the grader uses its own copy in the verifier image).
RUN rm -f /app/vimgolf-verifier.py
