# Quarkus target — docker-free build + native boot.
# Sourced by tests/test.sh. Provides: SUCCESS_PATTERN, FAILURE_PATTERN,
# DEPLOY_TIMEOUT and the fw_prepare / fw_build / fw_run functions.
# In scope from test.sh: $MVN, $SETTINGS.

SUCCESS_PATTERN="Listening on:"
FAILURE_PATTERN="BUILD FAILURE|\[ERROR\] \[ERROR\] Some problems were encountered while processing the POMs:|\[ERROR\] The build could not read [0-9]+ projects|\[FATAL\]|Malformed POM|ProjectBuildingException|ModelParseException|Failed to start application|Failed to start quarkus|stopped in|Unable to access jarfile"
DEPLOY_TIMEOUT=120

# Decide runtime args from the migrated config (ported from the old
# tests-quarkus Dockerfile): a %dev datasource profile boots under -Dquarkus.profile=dev;
# a prod external-DB kind is overridden to an in-memory H2 so the app can boot
# without a live database.
fw_prepare() {
    QUARKUS_ARGS=""
    if grep -rqE "%dev\.quarkus\.datasource" src 2>/dev/null; then
        QUARKUS_ARGS="-Dquarkus.profile=dev"
    elif grep -rhoP "^quarkus\.datasource\.db-kind\s*=\s*\K\S+" src 2>/dev/null | grep -qE "postgresql|mysql|mariadb|mssql|db2|oracle"; then
        QUARKUS_ARGS="-Dquarkus.datasource.db-kind=h2 -Dquarkus.datasource.jdbc.url=jdbc:h2:mem:app;DB_CLOSE_DELAY=-1 -Dquarkus.datasource.username=sa -Dquarkus.datasource.password="
    fi
    export QUARKUS_ARGS
    echo "[INFO] Quarkus args: ${QUARKUS_ARGS:-<none>}"

    # Detect the port the agent configured and export it for smoke tests.
    # Smoke tests read DAYTRADER_PORT (default 8080); if the agent used a
    # different port (e.g. 9080) all tests would fail with ECONNREFUSED.
    DETECTED_PORT=$(grep -rhoP "^quarkus\.http\.port\s*=\s*\K[0-9]+" src 2>/dev/null | head -1)
    if [ -n "$DETECTED_PORT" ] && [ "$DETECTED_PORT" != "8080" ]; then
        echo "[INFO] Detected quarkus.http.port=$DETECTED_PORT — setting DAYTRADER_PORT"
        export DAYTRADER_PORT="$DETECTED_PORT"
    fi

    # Detect the HTTP root path (context path) the agent configured and export
    # it for smoke tests. Smoke tests read DAYTRADER_CONTEXT_PATH (default "").
    DETECTED_ROOT=$(grep -rhoP "^quarkus\.http\.root-path\s*=\s*\K\S+" src 2>/dev/null | head -1)
    if [ -n "$DETECTED_ROOT" ] && [ "$DETECTED_ROOT" != "/" ]; then
        echo "[INFO] Detected quarkus.http.root-path=$DETECTED_ROOT — setting DAYTRADER_CONTEXT_PATH"
        export DAYTRADER_CONTEXT_PATH="$DETECTED_ROOT"
    fi

    # cargotracker/quarkus requires an ActiveMQ Artemis broker for JMS messaging.
    # The upstream eval-harness Dockerfile installs Artemis and starts it before
    # running the app. We do the same here: detect the Artemis home (installed by
    # the environment/Dockerfile at /opt/artemis) and start the broker.
    if grep -rqsE "artemis|amqp|jms" /app \
            --include='application.properties' \
            --include='application.yml' \
            --include='application.yaml' \
            --include='pom.xml' 2>/dev/null; then
        ARTEMIS_HOME="${ARTEMIS_HOME:-/opt/artemis}"
        ARTEMIS_BROKER="${ARTEMIS_BROKER:-/var/lib/artemis-broker}"
        if [ -x "$ARTEMIS_BROKER/bin/artemis-service" ]; then
            echo "[INFO] Starting ActiveMQ Artemis broker at $ARTEMIS_BROKER..."
            "$ARTEMIS_BROKER/bin/artemis-service" start 2>/dev/null || true
            # Wait up to 15s for the AMQP port (5672) to open.
            for _i in $(seq 1 15); do
                ss -tlnp 2>/dev/null | grep -q ':5672 ' && break
                sleep 1
            done
            echo "[INFO] Artemis broker started."
        else
            echo "[WARN] Artemis broker not found at $ARTEMIS_BROKER — app may fail JMS connections."
        fi
    fi
}

fw_build() {
    # Migration gate: compile counts only if the project is actually configured
    # as a Quarkus app. The unmigrated source (Jakarta war / Spring) builds fine
    # under `mvn install` but declares no quarkus-maven-plugin, which would score
    # compile=1 for a no-op run. Gate on the plugin so compile reflects migration.
    # Message stays distinct from the transient-network patterns so test.sh's
    # retry loop does not re-run it.
    if ! grep -rqs --include=pom.xml "quarkus-maven-plugin" /app 2>/dev/null; then
        echo "=== COMPILE FAIL === no quarkus-maven-plugin in any pom.xml — not migrated to Quarkus"
        return 1
    fi
    # IBM Semeru JDK 21 enforces stricter access than OpenJDK; ByteBuddy (used by
    # Hibernate during Quarkus augmentation) hits an IllegalAccessError on
    # AbstractList$Itr without these opens. Harmless on non-Semeru JVMs.
    local BYTEBUDDY_OPENS="--add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.lang=ALL-UNNAMED"
    export MAVEN_OPTS="${MAVEN_OPTS:-} ${BYTEBUDDY_OPENS}"
    # cart migrates to a runnable web module; build just it (+ its deps) so the
    # quarkus-run.jar is produced. Other apps are single-module.
    if [ -d cart-web ]; then
        $MVN $SETTINGS -Dmaven.wagon.http.retryHandler.count=3 -Dmaven.wagon.http.retryHandler.requestSent=true install -pl cart-web -am -Dmaven.test.skip=true $QUARKUS_ARGS
    else
        $MVN $SETTINGS -Dmaven.wagon.http.retryHandler.count=3 -Dmaven.wagon.http.retryHandler.requestSent=true install -Dmaven.test.skip=true $QUARKUS_ARGS
    fi
}

fw_run() {
    local runner
    # Prefer the fast-jar layout (target/quarkus-app/quarkus-run.jar). Fall back to
    # the uber-jar the instructions ask agents to build (target/<finalName>-runner.jar)
    # when no fast-jar is present — either is a valid Quarkus runnable, so score the
    # app the agent actually produced instead of failing deploy on packaging choice.
    runner=$(find . -name quarkus-run.jar -type f 2>/dev/null | head -1)
    [ -z "$runner" ] && runner=$(find . -path '*/target/*-runner.jar' -type f 2>/dev/null | head -1)
    # uber-jar with quarkus.package.jar.add-runner-suffix=false produces <name>.jar
    # (no -runner suffix); Quarkus records the artifact it built in
    # target/quarkus-artifact.properties.
    if [ -z "$runner" ]; then
        local props art
        for props in $(find . -path '*/target/quarkus-artifact.properties' -type f 2>/dev/null); do
            art=$(sed -n 's/^path=//p' "$props" | head -1)
            [ -n "$art" ] && [ -f "$(dirname "$props")/$art" ] && { runner="$(dirname "$props")/$art"; break; }
        done
    fi
    if [ -z "$runner" ]; then echo "=== DEPLOY FAIL === No quarkus-run.jar, *-runner.jar or quarkus-artifact.properties artifact found"; return 1; fi
    echo "[INFO] Launching runner: $runner"
    exec java $QUARKUS_ARGS -jar "$runner"
}
