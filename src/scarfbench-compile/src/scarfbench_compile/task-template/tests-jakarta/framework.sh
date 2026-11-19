# Jakarta EE target — docker-free build + native boot.
# Sourced by tests/test.sh. Provides: SUCCESS_PATTERN, FAILURE_PATTERN,
# DEPLOY_TIMEOUT and the fw_prepare / fw_build / fw_run functions.
# In scope from test.sh: $MVN, $SETTINGS.
#
# Two runtimes are supported:
#
#   Open Liberty  — liberty-maven-plugin; SUCCESS = CWWKF0011I
#   Payara/Cargo  — cargo-maven-plugin (cargotracker/jakarta); SUCCESS = "Payara 5"
#
# The runtime is auto-detected from pom.xml in fw_prepare().

DEPLOY_TIMEOUT=300

# The module that owns server.xml / liberty-maven-plugin (multi-module apps).
_liberty_dir() {
    local server_xml
    server_xml=$(find /app -path '*/src/main/liberty/config/server.xml' -not -path '*/target/*' | head -1)
    if [ -n "$server_xml" ]; then
        echo "${server_xml%/src/main/liberty/config/server.xml}"
    else
        dirname "$(find /app -name pom.xml -maxdepth 2 -not -path '*/target/*' | head -1 2>/dev/null || echo /app/pom.xml)"
    fi
}

# The Maven profile (if any) that activates the liberty-maven-plugin.
_liberty_profile() {
    awk '/<profile>/{inp=1;id=""} inp&&/<id>/&&id==""{l=$0;sub(/.*<id>/,"",l);sub(/<\/id>.*/,"",l);id=l} inp&&/liberty-maven-plugin/{print id;exit} /<\/profile>/{inp=0;id=""}' "$1/pom.xml" 2>/dev/null
}

fw_prepare() {
    # Detect runtime: Liberty takes priority over Cargo because some apps (e.g.
    # petclinic/jakarta) ship a mega-pom that references both plugins in
    # non-default profiles. If liberty-maven-plugin is present the agent must
    # have migrated to Liberty; only fall back to Cargo when Liberty is absent.
    if grep -rqs --include=pom.xml "liberty-maven-plugin" /app 2>/dev/null; then
        JAKARTA_RUNTIME="liberty"
        # CWWKZ0001I = "Application <name> started in N seconds." — fires only
        # after the WAR is fully deployed and REST endpoints are live.
        # CWWKF0011I (server ready) fires earlier, before the WAR is deployed,
        # causing smoke tests to hit 404s on still-loading endpoints.
        SUCCESS_PATTERN="CWWKZ0001I"
        FAILURE_PATTERN="BUILD FAILURE|\[ERROR\] \[ERROR\] Some problems were encountered while processing the POMs:|\[ERROR\] The build could not read [0-9]+ projects|\[FATAL\]|Malformed POM|ProjectBuildingException|ModelParseException|Failed to start application|stopped in|Unable to access jarfile"
        LIBERTY_DIR=$(_liberty_dir); export LIBERTY_DIR
        echo "[INFO] Jakarta runtime: Open Liberty (mvn liberty:run), module: $LIBERTY_DIR"
    elif grep -rqs --include=pom.xml "cargo-maven-plugin\|org\.codehaus\.cargo" /app 2>/dev/null; then
        JAKARTA_RUNTIME="cargo"
        # Match the Payara "ready" message, not the plugin loading string.
        # "cargo.maven2.plugin" appears immediately during plugin resolution —
        # before Payara has booted — and causes a false-positive DEPLOY OK.
        SUCCESS_PATTERN="Payara [0-9].*started on port|GlassFish.*started|Payara.*ready|cargo-tracker.*deployed"
        FAILURE_PATTERN="BUILD FAILURE|\[ERROR\] \[ERROR\] Some problems were encountered|\[FATAL\]|Malformed POM|ProjectBuildingException|ModelParseException|Failed to start application"
        echo "[INFO] Jakarta runtime: Payara/Cargo (mvn cargo:run)"
    else
        JAKARTA_RUNTIME="liberty"
        SUCCESS_PATTERN="CWWKZ0001I"
        FAILURE_PATTERN="BUILD FAILURE|\[ERROR\] \[ERROR\] Some problems were encountered while processing the POMs:|\[ERROR\] The build could not read [0-9]+ projects|\[FATAL\]|Malformed POM|ProjectBuildingException|ModelParseException|Failed to start application|stopped in|Unable to access jarfile"
        LIBERTY_DIR=$(_liberty_dir); export LIBERTY_DIR
        echo "[INFO] Jakarta runtime: Open Liberty (mvn liberty:run), module: $LIBERTY_DIR"
    fi
    export SUCCESS_PATTERN FAILURE_PATTERN JAKARTA_RUNTIME

    # Postgres: required by realworld/jakarta and petclinic/jakarta.
    # The exact user/db/password are read from the upstream eval-harness Dockerfiles:
    #   realworld/jakarta:  postgres_user / S3cret / postgres_db
    #   petclinic/jakarta:  petclinic_jakartaee / petclinic_jakartaeepwd / petclinic_jakartaee_liberty
    #
    # We detect which app this is by looking for the known datasource config in
    # the app source, then create the exact credentials the app expects.
    if grep -rqsE "postgresql|org\.postgresql" /app \
            --include='persistence.xml' \
            --include='server.xml' \
            --include='*.properties' 2>/dev/null; then
        echo "[INFO] Postgres datasource detected — starting local PostgreSQL..."
        if ! command -v pg_lsclusters >/dev/null 2>&1; then
            echo "[WARN] PostgreSQL not installed in this image — app may fail to start."
        else
            # Start whichever cluster exists.
            pg_ctlcluster "$(pg_lsclusters -h | awk '{print $1}' | head -1)" \
                          "$(pg_lsclusters -h | awk '{print $2}' | head -1)" \
                          start 2>/dev/null || true

            # Wait up to 15s for the socket.
            for _i in $(seq 1 15); do
                pg_isready -q 2>/dev/null && break
                sleep 1
            done

            # Provision credentials. Identify the app by the datasource config it
            # ships — each app has a unique database name that doesn't appear in others.
            if grep -rqsE "postgres_db|postgres_user" /app \
                    --include='persistence.xml' --include='server.xml' --include='*.properties' 2>/dev/null; then
                # realworld/jakarta
                su - postgres -c "psql -tc \"SELECT 1 FROM pg_user WHERE usename='postgres_user'\" | grep -q 1 || psql -c \"CREATE USER postgres_user WITH PASSWORD 'S3cret';\"" 2>/dev/null || true
                su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='postgres_db'\" | grep -q 1 || psql -c \"CREATE DATABASE postgres_db OWNER postgres_user;\"" 2>/dev/null || true
                su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE postgres_db TO postgres_user;\"" 2>/dev/null || true
                echo "[INFO] PostgreSQL: created postgres_user / postgres_db (realworld/jakarta)"
            elif grep -rqsE "petclinic_jakartaee" /app \
                    --include='persistence.xml' --include='server.xml' --include='*.properties' 2>/dev/null; then
                # petclinic/jakarta
                su - postgres -c "psql -tc \"SELECT 1 FROM pg_user WHERE usename='petclinic_jakartaee'\" | grep -q 1 || psql -c \"CREATE USER petclinic_jakartaee WITH PASSWORD 'petclinic_jakartaeepwd';\"" 2>/dev/null || true
                su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='petclinic_jakartaee_liberty'\" | grep -q 1 || psql -c \"CREATE DATABASE petclinic_jakartaee_liberty OWNER petclinic_jakartaee;\"" 2>/dev/null || true
                su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE petclinic_jakartaee_liberty TO petclinic_jakartaee;\"" 2>/dev/null || true
                echo "[INFO] PostgreSQL: created petclinic_jakartaee / petclinic_jakartaee_liberty (petclinic/jakarta)"
            else
                echo "[WARN] Unknown Postgres app — skipping credential provisioning; app may fail to connect."
            fi
        fi
    fi
}

fw_build() {
    if [ "${JAKARTA_RUNTIME:-liberty}" = "cargo" ]; then
        # Payara/Cargo: no migration gate needed (cargotracker uses a unique
        # plugin so a no-op unmigrated build would also fail the cargo:run stage).
        # Payara 5 (bundled by cargo-maven-plugin) only supports Java 11
        # (class file major version 55). The image runs JDK 21, so we must
        # compile down to release 11 or Payara will refuse to deploy the WAR
        # with "Unsupported class file major version 65".
        $MVN $SETTINGS -Dmaven.wagon.http.retryHandler.count=3 \
            -Dmaven.wagon.http.retryHandler.requestSent=true \
            -Dmaven.compiler.release=11 \
            package -Dmaven.test.skip=true
    else
        # Open Liberty migration gate: compile counts only if liberty-maven-plugin
        # is present. The unmigrated source (Quarkus / Spring) builds fine without it.
        if ! grep -rqs --include=pom.xml "liberty-maven-plugin" /app 2>/dev/null; then
            echo "=== COMPILE FAIL === no liberty-maven-plugin in any pom.xml — not migrated to Jakarta EE/Liberty"
            return 1
        fi
        # 1. install all modules so sibling deps resolve from the local repo.
        $MVN $SETTINGS -Dmaven.wagon.http.retryHandler.count=3 \
            -Dmaven.wagon.http.retryHandler.requestSent=true \
            install -Dmaven.test.skip=true || return 1
        # 2. provision the Liberty server before fw_run so it starts quickly.
        # liberty:deploy is included so that copyDependencies (e.g. Derby JARs)
        # are placed in the server lib dir before liberty:run starts. Without
        # this, apps that declare copyDependencies get 404s on REST endpoints
        # because the datasource driver is missing when the WAR initialises.
        # For apps without copyDependencies the deploy step is idempotent.
        local prof profarg
        prof=$(_liberty_profile "$LIBERTY_DIR")
        profarg=""; [ -n "$prof" ] && profarg="-P $prof"
        echo "[INFO] Liberty profile: ${prof:-<none>}"
        ( cd "$LIBERTY_DIR" && $MVN $SETTINGS \
            -Dmaven.wagon.http.retryHandler.count=3 \
            -Dmaven.wagon.http.retryHandler.requestSent=true \
            $profarg liberty:create liberty:install-feature liberty:deploy )
    fi
}

fw_run() {
    if [ "${JAKARTA_RUNTIME:-liberty}" = "cargo" ]; then
        # -Dcargo.wait=true ensures cargo:run blocks after deployment (default
        # behavior changed in cargo-maven3-plugin; without this it may exit
        # with BUILD SUCCESS once the container starts, tearing Payara down).
        exec $MVN $SETTINGS -Dcargo.wait=true cargo:run
    else
        local prof profarg
        prof=$(_liberty_profile "$LIBERTY_DIR")
        profarg=""; [ -n "$prof" ] && profarg="-P $prof"
        cd "$LIBERTY_DIR" && exec $MVN $SETTINGS $profarg liberty:run
    fi
}
