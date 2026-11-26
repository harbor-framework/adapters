# The published task images are built for linux/amd64 only.
FROM --platform=linux/amd64 {docker_image}

# The grader is a Python script. Some task images ship without Python.
RUN if ! command -v python3 >/dev/null 2>&1; then \
        if command -v apt-get >/dev/null 2>&1; then \
            (apt-get -o Acquire::AllowReleaseInfoChange=true update || true) && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*; \
        elif command -v apk >/dev/null 2>&1; then apk add --no-cache python3; \
        elif command -v dnf >/dev/null 2>&1; then dnf install -y python3; \
        elif command -v yum >/dev/null 2>&1; then yum install -y python3; \
        else echo "no supported package manager to install python3" >&2; exit 1; fi; \
    fi

{image_fixup}

COPY . /tests/

WORKDIR {working_dir}
