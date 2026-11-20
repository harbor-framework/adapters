# Separate verifier image: same pinned Python as the task image, so
# agent-written code (e.g. max_tokens game_of_life.py) is checked under
# the interpreter it targeted. Tests are bundled at build time.
FROM {base_image}
COPY . /tests/
