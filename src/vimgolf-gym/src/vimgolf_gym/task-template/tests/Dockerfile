# Verifier sandbox: same published upstream image that vimgolf-evaluate.py runs
# (agile4im/vimgolf-verifier:v0.0.3, /app/vimgolf-verifier.py), plus the grader.
FROM agile4im/vimgolf-verifier:v0.0.3@sha256:be597cfda162160ab3f6be0ce5897314957845bfbb758a884ddc721b5046c8da
# The image's ENTRYPOINT is ["sh"], which would turn Harbor's `sh -c "sleep infinity"`
# into `sh sh -c ...` (exit 2); clear it.
ENTRYPOINT []

COPY test.sh grade.py grading.json /tests/
RUN chmod 700 /tests && chmod 600 /tests/grading.json && chmod 700 /tests/test.sh /tests/grade.py
