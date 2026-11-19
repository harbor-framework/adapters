# Spring Boot target — docker-free build + native boot.
# Sourced by tests/test.sh. Provides: SUCCESS_PATTERN, FAILURE_PATTERN,
# DEPLOY_TIMEOUT and the fw_prepare / fw_build / fw_run functions.
# In scope from test.sh: $MVN, $SETTINGS.

SUCCESS_PATTERN="Started .*Application"
FAILURE_PATTERN="BUILD FAILURE|\[ERROR\] COMPILATION ERROR|COMPILATION ERROR|\[ERROR\] Failed to execute goal|\[FATAL\]|MojoExecutionException|ProjectBuildingException|ModelParseException|Failed to start application|cannot find symbol|package .* does not exist| error:|APPLICATION FAILED TO START|BeanCreationException|UnsatisfiedDependencyException|Unable to access jarfile"
DEPLOY_TIMEOUT=120

# Gradle-only Spring apps ship an older wrapper that needs JDK 11; Maven builds
# keep using the image's JDK 21. JDK 11 is provided by environment/Dockerfile.
JDK11="${JDK11:-/opt/java/openjdk-11}"

fw_prepare() {
    # The verifier has no database service (the benchmark's docker-compose/dev
    # services are not available). If the migrated app is configured for a
    # server database but bundles H2, run it against in-memory H2 instead, as the
    # Quarkus target does. Apps that do not ship H2 are left alone and fail on
    # their own (no embedded DB available).
    SPRING_DB_OVERRIDE=false
    if grep -rhoE "^\s*spring\.datasource\.url\s*[=:].*jdbc:(postgresql|mysql|mariadb|sqlserver|db2|oracle)" \
         --include='application*.properties' --include='application*.yml' --include='application*.yaml' src 2>/dev/null | grep -q .; then
        SPRING_DB_OVERRIDE=true
    fi
    export SPRING_DB_OVERRIDE
}

# Called from fw_run once the runnable jar is known.
_spring_db_env() {
    local jar=$1
    [ "$SPRING_DB_OVERRIDE" = "true" ] || return 0
    if [ -n "$jar" ] && unzip -l "$jar" 2>/dev/null | grep -qE 'BOOT-INF/lib/h2-[0-9]'; then
        echo "[INFO] Server database configured but H2 is bundled — running against in-memory H2"
        export SPRING_DATASOURCE_URL="jdbc:h2:mem:app;DB_CLOSE_DELAY=-1;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE"
        export SPRING_DATASOURCE_USERNAME=sa SPRING_DATASOURCE_PASSWORD=
        export SPRING_DATASOURCE_DRIVER_CLASS_NAME=org.h2.Driver
        export SPRING_JPA_PROPERTIES_HIBERNATE_DIALECT=org.hibernate.dialect.H2Dialect
    else
        echo "[INFO] Server database configured and no H2 bundled — no embedded DB to fall back on"
    fi
}

fw_build() {
    # `-Dcheckstyle.skip=true`: some apps (e.g. petclinic) bind Spring's nohttp
    # checkstyle to `validate`; it fails on the http:// URL in settings.xml.
    # Irrelevant to the compile/deploy/health metric.
    # Migration gate: compile counts only if the project is actually configured
    # as a Spring Boot app. The unmigrated source (Jakarta war / Quarkus) builds
    # fine but declares no Spring Boot plugin, which would score compile=1 for a
    # no-op run. Gate on the plugin (Maven plugin / Gradle boot plugin) so compile
    # reflects migration. Message stays distinct from the transient-network
    # patterns so test.sh's retry loop does not re-run it.
    if [ -f pom.xml ]; then
        if ! grep -rqs --include=pom.xml "spring-boot-maven-plugin" /app 2>/dev/null; then
            echo "=== COMPILE FAIL === no spring-boot-maven-plugin in any pom.xml — not migrated to Spring Boot"
            return 1
        fi
        $MVN $SETTINGS -Dmaven.wagon.http.retryHandler.count=3 -Dmaven.wagon.http.retryHandler.requestSent=true install -Dmaven.test.skip=true -Dcheckstyle.skip=true -Dspring-javaformat.skip=true
    elif [ -f build.gradle ] || [ -f build.gradle.kts ]; then
        if ! grep -rEqs "org\.springframework\.boot" /app --include=build.gradle --include=build.gradle.kts 2>/dev/null; then
            echo "=== COMPILE FAIL === no Spring Boot Gradle plugin — not migrated to Spring Boot"
            return 1
        fi
        chmod +x gradlew 2>/dev/null || true
        JAVA_HOME="$JDK11" ./gradlew bootJar -x test --no-daemon
    else
        echo "=== COMPILE FAIL === no pom.xml or build.gradle found"; return 1
    fi
}

# Pick the *runnable* jar, not just the first one found. In multi-module builds
# `find | head -1` can grab a non-executable sibling or an unpacked dependency
# jar (BOOT-INF/lib, WEB-INF/lib). Prefer the Spring Boot repackaged fat jar
# (identified by its *.jar.original sibling), else the first jar whose manifest
# declares a Main-Class; last resort spring-boot:run from the app's pom.
fw_run() {
    local cands jar j pom_dir
    cands=$(find . \( -path "*/target/*.jar" -o -path "*/build/libs/*.jar" \) ! -path "*/WEB-INF/*" ! -path "*/BOOT-INF/*" ! -path "*/quarkus-app/*" ! -name "*-sources.*" ! -name "*-original.*" ! -name "*-plain.jar" ! -name "maven-wrapper.jar" -type f 2>/dev/null)
    jar=""
    for j in $cands; do if [ -f "$j.original" ]; then jar="$j"; break; fi; done
    if [ -z "$jar" ]; then
        for j in $cands; do if unzip -p "$j" META-INF/MANIFEST.MF 2>/dev/null | grep -q '^Main-Class:'; then jar="$j"; break; fi; done
    fi
    # -Xshareclasses:none: the base image's JAVA_TOOL_OPTIONS enables OpenJ9's
    # read-only shared class cache, which on amd64 makes JoinFaces' classpath scan
    # fail with "OutOfMemoryError: Required array size too large" at startup.
    if [ -n "$jar" ]; then _spring_db_env "$jar"; echo "[INFO] Launching runnable jar: $jar"; exec java -Xshareclasses:none -jar "$jar"; fi
    pom_dir=$(dirname "$(find /app -name pom.xml -maxdepth 2 -not -path '*/target/*' | head -1 2>/dev/null || echo /app/pom.xml)")
    echo "[INFO] No runnable jar found; falling back to spring-boot:run in $pom_dir"
    cd "$pom_dir" && exec $MVN $SETTINGS -Dmaven.test.skip=true spring-boot:run
}
