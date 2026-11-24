# Separate verifier image: verify.py needs only the Python standard
# library. Tests (and the outcome integrity key) are bundled at build
# time and never present in the agent container.
FROM {verifier_image}
COPY . /tests/
