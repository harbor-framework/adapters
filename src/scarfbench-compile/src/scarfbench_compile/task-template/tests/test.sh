#!/bin/bash
# Docker-free ScarfBench-Compile verifier: compile + deploy + HTTP health.
#
# Runs entirely inside the verifier container (same toolchain image as the
# agent). No Docker daemon required. Identical to the scarfbench verifier
# through the deploy stage; the smoke-test stage is replaced by a generic
# HTTP health probe.
#
# Stages:
#   1. fw_prepare()  — service overrides, env setup (sources framework.sh)
#   2. fw_build()    — mvn/gradle install with transient-failure retries
#   3. fw_run()      — native Java boot as a background process
#   4. Deploy wait   — watch logs for SUCCESS_PATTERN
#   5. Health        — HTTP probe of the app's real endpoint (any port/base path)
#
# Per-framework build/run logic lives in /tests/framework.sh (one of
# tests-{quarkus,spring,jakarta}/framework.sh, chosen at task generation).
set -uo pipefail

cd /app

APP_DIR=/app
LOG=/tmp/app.log
REWARD_FILE=/logs/verifier/reward.json
mkdir -p "$(dirname "$REWARD_FILE")" 2>/dev/null || true

rewards='{"compile": 0, "deploy": 0, "health": 0}'
emit() { echo "$rewards" > "$REWARD_FILE" 2>/dev/null || echo "$rewards" > /tmp/reward.json; }

# Use the image's system Maven. The app's ./mvnw wrapper bootstraps from
# repo.maven.apache.org (blocked by the mirror) so we avoid it.
#
# -U (--update-snapshots) forces Maven to re-attempt resolutions it previously
# cached as failed. The Google mirror HAS every artifact we need (incl.
# liberty-maven-plugin), but a single transient blip (429/network) on the first
# resolve writes a `.lastUpdated` "not found" marker that Maven then honours for
# the rest of the update interval — so the build-retry loop below re-runs but
# keeps hitting the SAME cached miss and never recovers. -U makes each retry a
# real re-fetch. Applies to every $MVN build/run call (jakarta liberty + cargo,
# spring, quarkus).
export MVN="mvn -U"
export SETTINGS=""; [ -f /tests/settings.xml ] && export SETTINGS="-s /tests/settings.xml"

# Retryable (network/mirror) build failures.
TRANSIENT="Connection reset|Could not transfer artifact|Remote host terminated|SSLHandshakeException|Failed to read artifact descriptor|could not be resolved|PluginResolutionException|Could not resolve dependencies|Received fatal alert|Premature end of Content-Length|Corrupted|checksum"

APP_PID=""
cleanup() {
    [ -n "$APP_PID" ] && kill "$APP_PID" 2>/dev/null || true
    [ -n "$APP_PID" ] && pkill -P "$APP_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Framework-specific build/run logic + patterns.
source /tests/framework.sh
fw_prepare

# ============================ Stage 1: COMPILE ============================
echo "=== COMPILE START ==="
BUILD_OK=false
for attempt in 1 2 3; do
    build_output=$(fw_build 2>&1); build_exit=$?
    echo "$build_output" | tail -40
    if [ $build_exit -eq 0 ]; then BUILD_OK=true; break; fi
    if echo "$build_output" | grep -qE "$TRANSIENT"; then
        echo "[WARN] Transient build failure, attempt $attempt/3"
        [ $attempt -lt 3 ] && { sleep 10; continue; }
    fi
    break
done
if $BUILD_OK; then
    echo "=== COMPILE OK ==="
    rewards=$(echo "$rewards" | jq '.compile = 1')
else
    echo "=== COMPILE FAIL ==="; emit; exit 0
fi

# ============================ Stage 2: DEPLOY =============================
echo "=== DEPLOY START ==="
: > "$LOG"
( fw_run ) >"$LOG" 2>&1 &
APP_PID=$!
echo "[INFO] Launched app (pid $APP_PID), watching for startup..."

deploy_ok=false
for i in $(seq 1 "${DEPLOY_TIMEOUT:-120}"); do
    if grep -Eq "$FAILURE_PATTERN" "$LOG"; then echo "[WARN] Failure pattern matched in log"; break; fi
    if grep -Eq "$SUCCESS_PATTERN" "$LOG"; then deploy_ok=true; break; fi
    if ! kill -0 "$APP_PID" 2>/dev/null; then
        # Process exited — do one final log check before declaring failure.
        # Payara/cargo:run can finish deploying and exit (BUILD SUCCESS) before
        # the 1-second polling loop reads the log.
        if grep -Eq "$SUCCESS_PATTERN" "$LOG"; then deploy_ok=true; fi
        echo "[WARN] App process exited early"
        break
    fi
    sleep 1
done

if $deploy_ok; then
    echo "=== DEPLOY OK ==="
    rewards=$(echo "$rewards" | jq '.deploy = 1')
else
    echo "[WARN] No success pattern matched in launch log — deploy=0."
    echo "--- last 60 lines of launch log ---"; tail -60 "$LOG" 2>/dev/null
    echo "--- end launch log ---"
fi

# ============================ Stage 3: HEALTH ============================
# Health passes when the app returns HTTP 200 (never a 404 — that was the old
# false-positive). The catch: a correctly-migrated app serves its real endpoint
# under a framework-specific BASE PATH the bare context root does not capture.
# cart's real health endpoint is /cart/api/cart/health (Quarkus root-path /cart
# + JAX-RS @Path /api/cart + method /health), NOT /cart — so probing only the
# health_check.sh context root scored a perfect migration health=0.
#
# So, instead of one guessed path, we reconstruct candidate URLs at runtime the
# same way the scarfbench eval-harness smoke suites discover a base — sweeping
#   {candidate ports} x {context prefixes} x {resource paths + health suffixes}
# and accepting the first HTTP 200. Prefixes and resource paths are read from
# the app's OWN config + JAX-RS/Spring/servlet annotations, so this holds for
# any valid migration regardless of the port/root-path the agent picked. Deploy
# is scored independently above and is never inferred from health.
#
# TWO narrow exceptions to strict-200, both applied ONLY after the strict-200
# sweep fails and both proof-of-mapping (the opposite of the old 404 false
# positive), never accepted on the bare root / generic-health / static paths:
#
#   1. 405 on a SOURCE-DECLARED route (RESOURCES): a GET to a route that only
#      accepts POST/PUT returns 405 under JAX-RS/RESTEasy (Jakarta/Quarkus) —
#      the framework matched the path but not the method, so the route is really
#      mapped and the app deployed.
#
#   2. A WebSocket UPGRADE HANDSHAKE (101 Switching Protocols, or 400 for a
#      rejected handshake) on a SOURCE-DECLARED WebSocket endpoint. Some apps
#      (e.g. taskcreator's Spring port: a @PostMapping controller GET-404s and
#      there is no static page) expose only a WebSocket. A GET with the upgrade
#      headers to a mapped @ServerEndpoint / registry.addHandler(...) path yields
#      101 (handshake accepted) — as unambiguous as a 200. Spring's Boot 3.5
#      PathPatternParser returns 404 (NOT 405) for GET on a POST-only route, so
#      the WebSocket handshake is the only legitimate non-404 signal for those.
echo "[INFO] Probing for HTTP 200 on the app's real endpoint (any port/base path)..."
HEALTH_OK=false

# health_check.sh's own BASE_URL path (the upstream contract endpoint), kept as
# both a context prefix and — via health_check.sh itself — a first-class probe.
# Empty means the server root.
HEALTH_PATH=""
if [ -f /tests/health_check.sh ]; then
    HC_DEFAULT=$(grep -oP 'BASE_URL:-\K[^}"]+' /tests/health_check.sh | head -1)
    HEALTH_PATH=$(echo "$HC_DEFAULT" | sed -E 's#^https?://[^/]+##')
fi

# Standard framework liveness endpoints (Quarkus SmallRye, Spring Actuator,
# Liberty MicroProfile). Probed at the server root AND under each context prefix.
GENERIC_HEALTH_PATHS="/q/health /q/health/live /q/health/ready /health /actuator/health /healthz"
# Suffixes appended to each discovered resource base (e.g. a @Path("/api/cart")
# resource with a method @Path("/health")).
HEALTH_SUFFIXES="/health /q/health"

# --- Context prefixes: where the app mounts its routes ----------------------
# Quarkus quarkus.http.root-path (prefixes everything) and quarkus.rest.path
# (JAX-RS base), Spring server.servlet.context-path AND camelCase contextPath,
# Liberty contextRoot, JAX-RS @ApplicationPath, plus health_check.sh's own base
# and the bare server root.
PREFIXES=$(
    {
        printf '%s\n' "" "$HEALTH_PATH"
        grep -rhoP 'quarkus\.http\.root-path\s*[=:]\s*\K\S+' /app --include='application.properties' --include='application.yml' --include='application.yaml' 2>/dev/null
        grep -rhoP 'quarkus\.rest\.path\s*[=:]\s*\K\S+' /app --include='application.properties' --include='application.yml' --include='application.yaml' 2>/dev/null
        grep -rhoP 'server\.(?:servlet\.)?context-?[Pp]ath\s*[=:]\s*\K\S+' /app --include='application.properties' --include='application.yml' --include='application.yaml' 2>/dev/null
        # spring.mvc.servlet.path relocates the DispatcherServlet, so it prefixes
        # EVERY Spring MVC mapping — REST controllers AND WebSocket handshakes
        # (e.g. taskcreator's =/taskcreator puts /taskinfo at /taskcreator/taskinfo
        # and the /wsinfo handshake at /taskcreator/wsinfo).
        grep -rhoP 'spring\.mvc\.servlet\.path\s*[=:]\s*\K\S+' /app --include='application.properties' --include='application.yml' --include='application.yaml' 2>/dev/null
        grep -rhoP 'contextRoot="\K[^"]+' /app --include='server.xml' 2>/dev/null
        grep -rhoP '@ApplicationPath\(\s*"\K[^"]+' /app --include='*.java' 2>/dev/null
        # Liberty derives the context root from the WAR name when server.xml's
        # <application>/<webApplication> gives a location but no explicit
        # contextRoot (e.g. location="timersession.war" -> /timersession).
        grep -rhoP 'location="\K[^"]+\.war' /app --include='server.xml' 2>/dev/null | sed -E 's#\.war$##; s#.*/##'
    } | sed -E 's#["'\'']##g'
)

# --- Resource bases: class/method routes declared in the source -------------
# JAX-RS @Path, Spring @RequestMapping/@GetMapping/@PostMapping, @WebServlet
# url patterns, and web.xml <url-pattern>. Templated ({id}) and wildcard/glob
# patterns are dropped — they can't be probed blind.
RESOURCES=$(
    {
        grep -rhoP '@Path\(\s*"\K[^"]+' /app --include='*.java' 2>/dev/null
        grep -rhoP '@(?:RequestMapping|GetMapping|PostMapping)\(\s*(?:(?:value|path)\s*=\s*)?\{?\s*"\K[^"]+' /app --include='*.java' 2>/dev/null
        grep -rhoP '@WebServlet\([^)]*\)' /app --include='*.java' 2>/dev/null | grep -oP '"\K/[^"]*'
        grep -rhoP '<url-pattern>\s*\K[^<]+' /app --include='web.xml' 2>/dev/null
    } | sed -E 's#/\*+$##' | grep -vP '[*{}]' | awk 'NF'
)

# --- Static entry pages: apps with no REST endpoint (e.g. a WebSocket demo)
# still serve a landing page. Collect web pages from the framework web roots —
# Quarkus/Jakarta META-INF/resources, Spring static/public, WAR src/main/webapp
# — as paths relative to that root (index.html -> /index.html). Quarkus serves
# these by exact path (not at "/"), so /index.html is the real 200. WEB-INF and
# build output (target/) are excluded; only HTML/JSP/JSF/XHTML pages are probed.
STATIC_PATHS=$(
    find /app -type f -not -path '*/target/*' \
        \( -path '*/META-INF/resources/*' -o -path '*/src/main/resources/static/*' \
           -o -path '*/src/main/resources/public/*' -o -path '*/src/main/webapp/*' \) \
        2>/dev/null \
      | grep -vE '/WEB-INF/' \
      | grep -iE '\.(html?|jsp|jsf|xhtml)$' \
      | sed -E 's#^.*/(META-INF/resources|src/main/resources/static|src/main/resources/public|src/main/webapp)/##' \
      | awk 'NF'
)

# --- Query parameters: some endpoints 400 without a required param ----------
# hello-servlet's /greeting returns HTTP 400 unless ?name= is supplied (both the
# JAX-RS @QueryParam and the Spring variant, which explicitly rejects a blank
# name). Collect JAX-RS @QueryParam, Spring @RequestParam (explicit name= /
# value=, or the Java parameter identifier), and servlet request.getParameter
# names, then probe each resource both bare AND with every discovered param set
# to a benign value (1). Servers ignore unknown extra params, so one combined
# query string is safe to append everywhere.
QUERY_PARAMS=$(
    {
        grep -rhoP '@QueryParam\(\s*"\K[^"]+' /app --include='*.java' 2>/dev/null
        grep -rhoP '@RequestParam\(\s*(?:(?:value|name)\s*=\s*)?"\K[^"]+' /app --include='*.java' 2>/dev/null
        grep -rhoP '@RequestParam\([^)]*\)\s+(?:final\s+)?[\w.<>\[\],]+\s+\K\w+' /app --include='*.java' 2>/dev/null
        grep -rhoP 'getParameter\(\s*"\K[^"]+' /app --include='*.java' 2>/dev/null
    } | grep -vP '[{}]' | awk 'NF && !seen[$0]++'
)
QUERY_STRING=""
while IFS= read -r qp; do
    [ -z "$qp" ] && continue
    QUERY_STRING="${QUERY_STRING}${QUERY_STRING:+&}${qp}=1"
done <<< "$QUERY_PARAMS"

# --- SOAP / JAX-WS endpoints: a GET returns the WSDL (200), never the operation.
# Discover the service base from Quarkus CXF (quarkus.cxf.path), Spring WS
# (DefaultWsdl11Definition.setLocationUri, MessageDispatcherServlet mapping), and
# service names from Spring @Bean(name=...) / JAX-WS @WebService(serviceName=...).
# Probe each base bare and with ?wsdl/.wsdl, plus base/<name>?wsdl|.wsdl. Quarkus
# CXF serves a 200 service list at the bare path; Spring WS serves the WSDL at
# <base>/<bean>.wsdl; JAX-WS serves it at the endpoint address + ?wsdl.
# Files carrying a plain JAX-WS endpoint (@WebService, no CXF/Spring-WS base).
# On Liberty the WSDL hangs off the app context root, so there's no separate
# base config to read — the context prefixes ARE the bases.
WS_FILES=$(grep -rlP '@WebService' /app --include='*.java' 2>/dev/null)
SOAP_BASES=$(
    {
        grep -rhoP 'quarkus\.cxf\.path\s*[=:]\s*\K\S+' /app --include='application.properties' --include='application.yml' --include='application.yaml' 2>/dev/null
        grep -rhoP 'setLocationUri\(\s*"\K[^"]+' /app --include='*.java' 2>/dev/null
        grep -rhoP 'ServletRegistrationBean[^;]*?"\K/[^"*]+' /app --include='*.java' 2>/dev/null
        [ -n "$WS_FILES" ] && printf '%s\n' "$PREFIXES"
    } | sed -E 's#["'\'']##g; s#/\*+$##; s#/+$##' | awk 'NF && !seen[$0]++'
)
SOAP_NAMES=$(
    {
        grep -rhoP '@Bean\(\s*name\s*=\s*"\K[^"]+' /app --include='*.java' 2>/dev/null
        grep -rhoP '@WebService\([^)]*serviceName\s*=\s*"\K[^"]+' /app --include='*.java' 2>/dev/null
        # JAX-WS default service name is <ClassName>Service (also try the bare
        # class name), for @WebService beans with no explicit serviceName.
        while IFS= read -r f; do
            [ -z "$f" ] && continue
            cn=$(grep -oP 'public\s+(?:final\s+)?class\s+\K\w+' "$f" 2>/dev/null | head -1)
            [ -n "$cn" ] && printf '%s\n%sService\n' "$cn" "$cn"
        done <<< "$WS_FILES"
    } | sed -E 's#["'\'']##g' | awk 'NF && !seen[$0]++'
)
SOAP_PATHS=$(
    {
        while IFS= read -r b; do
            [ -z "$b" ] && continue
            b="/${b#/}"; b="${b%/}"
            printf '%s\n' "$b" "${b}?wsdl" "${b}.wsdl"
            while IFS= read -r n; do
                [ -z "$n" ] && continue
                printf '%s\n' "${b}/${n}?wsdl" "${b}/${n}.wsdl"
            done <<< "$SOAP_NAMES"
        done <<< "$SOAP_BASES"
    } | awk 'NF && !seen[$0]++'
)

# --- WebSocket endpoints: for apps whose only surface is a WebSocket -----------
# Jakarta/Quarkus declare @ServerEndpoint("/path"); Spring registers handlers via
# registry.addHandler(handler, "/path"). Templated/glob paths are dropped.
WS_PATHS=$(
    {
        grep -rhoP '@ServerEndpoint\(\s*"\K[^"]+' /app --include='*.java' 2>/dev/null
        grep -rhoP 'addHandler\([^)]*?"\K/[^"]+' /app --include='*.java' 2>/dev/null
    } | sed -E 's#["'\'']##g' | grep -vP '[*{}]' | awk 'NF && !seen[$0]++'
)

# --- Compose the candidate path set (path portion only), then dedupe --------
# For each prefix: the prefix root, its /index.html welcome page, generic-health
# paths, each resource (bare, with the discovered query string, and + health
# suffix), and each discovered static page. Then SOAP/WSDL paths (absolute, at
# the server root). Collapse // and drop blanks.
CANDIDATE_PATHS=$(
    {
        while IFS= read -r p; do
            [ -n "$p" ] && { p="/${p#/}"; p="${p%/}"; }
            printf '%s\n' "${p}/" "${p}/index.html"
            for h in $GENERIC_HEALTH_PATHS; do printf '%s\n' "${p}${h}"; done
            while IFS= read -r r; do
                [ -z "$r" ] && continue
                r="/${r#/}"; r="${r%/}"
                printf '%s\n' "${p}${r}"
                [ -n "$QUERY_STRING" ] && printf '%s\n' "${p}${r}?${QUERY_STRING}"
                for h in $HEALTH_SUFFIXES; do printf '%s\n' "${p}${r}${h}"; done
            done <<< "$RESOURCES"
            while IFS= read -r s; do
                [ -z "$s" ] && continue
                printf '%s\n' "${p}/${s#/}"
            done <<< "$STATIC_PATHS"
        done <<< "$PREFIXES"
        [ -n "$SOAP_PATHS" ] && printf '%s\n' "$SOAP_PATHS"
    } | sed -E 's#//+#/#g' | awk 'NF && !seen[$0]++'
)

# --- Method-mismatch fallback set: bare source-declared routes only ----------
# {prefix} x {resource}, no health suffix / query / static. A GET here that
# returns 405 proves the route is mapped (the app is up and migrated correctly)
# even when the route only accepts POST/PUT and the app ships no GET-able page.
# Probed only after the strict-200 sweep, and 405 is accepted ONLY for these.
ROUTE_PATHS=$(
    {
        while IFS= read -r p; do
            [ -n "$p" ] && { p="/${p#/}"; p="${p%/}"; }
            while IFS= read -r r; do
                [ -z "$r" ] && continue
                r="/${r#/}"; r="${r%/}"
                printf '%s\n' "${p}${r}"
            done <<< "$RESOURCES"
        done <<< "$PREFIXES"
    } | sed -E 's#//+#/#g' | awk 'NF && !seen[$0]++'
)

# --- WebSocket candidate paths: {prefix} x {ws endpoint}. WS endpoints are
# usually root-absolute, but a context-path/root-path still prefixes them, so we
# probe the bare path AND under each context prefix.
WS_CANDIDATES=$(
    {
        while IFS= read -r w; do
            [ -z "$w" ] && continue
            w="/${w#/}"; w="${w%/}"
            while IFS= read -r p; do
                [ -n "$p" ] && { p="/${p#/}"; p="${p%/}"; }
                printf '%s\n' "${p}${w}"
            done <<< "$PREFIXES"
        done <<< "$WS_PATHS"
    } | sed -E 's#//+#/#g' | awk 'NF && !seen[$0]++'
)

probe() { curl -sL -o /dev/null -w '%{http_code}' --max-time 4 "$1" 2>/dev/null | tr -d '[:space:]'; }
# WebSocket handshake probe: a mapped endpoint answers the upgrade with 101
# Switching Protocols; a rejected handshake on a mapped endpoint returns 400.
# Both prove the route exists (a missing path 404s). Fixed 16-byte nonce key.
ws_probe() {
    curl -s -o /dev/null -w '%{http_code}' --max-time 4 \
        -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
        -H 'Sec-WebSocket-Version: 13' \
        -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
        "$1" 2>/dev/null | tr -d '[:space:]'
}

echo "[INFO] Context prefixes: $(echo "$PREFIXES" | awk 'NF{printf "%s ",$0}')| health_check path: ${HEALTH_PATH:-/}"
echo "[INFO] $(echo "$CANDIDATE_PATHS" | grep -c .) candidate paths per port | query: ${QUERY_STRING:-none} | soap bases: $(echo "$SOAP_BASES" | awk 'NF{printf "%s ",$0}')"

for attempt in $(seq 1 "${HEALTH_RETRIES:-10}"); do
    DEPLOY_OUTPUT=$(cat "$LOG" 2>/dev/null)
    # Candidate ports: live listening sockets, deploy-log announcements, config
    # files under /app, then framework defaults. Re-scanned each attempt because
    # the socket may bind a moment after "Listening on:".
    APP_PORTS=""
    APP_PORTS="$APP_PORTS $(ss -tlnp 2>/dev/null | grep LISTEN | grep -oP '(?:\*:|0\.0\.0\.0:|127\.0\.0\.1:|\[::\]:)\K\d+')"
    APP_PORTS="$APP_PORTS $(netstat -tlnp 2>/dev/null | grep -i java | grep -oP ':\K\d+')"
    APP_PORTS="$APP_PORTS $(lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | grep -oP ':\K\d+')"
    APP_PORTS="$APP_PORTS $(echo "$DEPLOY_OUTPUT" | grep -oP 'Listening on:.*?:\K\d+')"
    APP_PORTS="$APP_PORTS $(echo "$DEPLOY_OUTPUT" | grep -oP 'Tomcat started on port\(?s?\)? \K\d+')"
    APP_PORTS="$APP_PORTS $(echo "$DEPLOY_OUTPUT" | grep -oP 'CWWKT0016I.*?http://[^/]*:\K\d+')"
    APP_PORTS="$APP_PORTS $(grep -rhoP '(?:quarkus\.http\.port|server\.port)\s*[=:]\s*\K\d+' /app --include='application.properties' --include='application.yml' --include='application.yaml' 2>/dev/null)"
    APP_PORTS="$APP_PORTS 8080 9080"
    # Normalise: valid ports, drop the JDWP debug port, dedupe (stable order).
    APP_PORTS=$(echo "$APP_PORTS" | tr ' ' '\n' | grep -xP '\d+' | grep -v '^5005$' | awk '!seen[$0]++' | tr '\n' ' ')
    [ "$attempt" -eq 1 ] && echo "[INFO] Candidate ports: $APP_PORTS"

    for APP_PORT in $APP_PORTS; do
        # (a) health_check.sh's own contract endpoint (it appends its internal
        #     suffix, e.g. realworld's /tags, to the BASE_URL we hand it).
        if [ -f /tests/health_check.sh ] && \
           BASE_URL="http://localhost:${APP_PORT}${HEALTH_PATH}" timeout 15 bash /tests/health_check.sh >/dev/null 2>&1; then
            echo "[INFO] Health OK: port ${APP_PORT} via health_check.sh (${HEALTH_PATH:-/})"
            HEALTH_OK=true; break
        fi
        # (b) reconstructed real endpoints — first HTTP 200 wins.
        while IFS= read -r path; do
            [ -z "$path" ] && continue
            if [ "$(probe "http://localhost:${APP_PORT}${path}")" = "200" ]; then
                echo "[INFO] Health OK: HTTP 200 on port ${APP_PORT} path ${path}"
                HEALTH_OK=true; break
            fi
        done <<< "$CANDIDATE_PATHS"
        $HEALTH_OK && break
        # (c) method-mismatch fallback — a 405 on a SOURCE-DECLARED route proves
        #     the route is mapped (app deployed) even with no GET surface.
        while IFS= read -r path; do
            [ -z "$path" ] && continue
            code=$(probe "http://localhost:${APP_PORT}${path}")
            if [ "$code" = "200" ] || [ "$code" = "405" ]; then
                echo "[INFO] Health OK: HTTP ${code} on declared route port ${APP_PORT} path ${path}"
                HEALTH_OK=true; break
            fi
        done <<< "$ROUTE_PATHS"
        $HEALTH_OK && break
        # (d) WebSocket handshake — a 101 (or 400 rejected-handshake) on a
        #     SOURCE-DECLARED WebSocket endpoint proves the route is mapped,
        #     for apps whose only surface is a WebSocket (Spring GET-404s them).
        while IFS= read -r path; do
            [ -z "$path" ] && continue
            code=$(ws_probe "http://localhost:${APP_PORT}${path}")
            if [ "$code" = "101" ] || [ "$code" = "400" ]; then
                echo "[INFO] Health OK: WebSocket handshake HTTP ${code} on port ${APP_PORT} path ${path}"
                HEALTH_OK=true; break
            fi
        done <<< "$WS_CANDIDATES"
        $HEALTH_OK && break
    done
    $HEALTH_OK && break
    sleep 3
done

if $HEALTH_OK; then
    rewards=$(echo "$rewards" | jq '.health = 1')
else
    echo "[WARN] Health check failed — no candidate port/path returned HTTP 200 (nor 405 on a declared route, nor a WebSocket handshake)."
    echo "[DEBUG] RESOURCES=[$(echo "$RESOURCES" | tr '\n' ' ')]"
    echo "[DEBUG] ROUTE_PATHS=[$(echo "$ROUTE_PATHS" | tr '\n' ' ')]"
    echo "[DEBUG] WS_CANDIDATES=[$(echo "$WS_CANDIDATES" | tr '\n' ' ')]"
    echo "[DEBUG] observed HTTP codes on declared routes / WebSocket endpoints:"
    for dbg_port in ${APP_PORTS:-9080 8080}; do
        while IFS= read -r path; do
            [ -z "$path" ] && continue
            echo "  GET :${dbg_port}${path} -> $(probe "http://localhost:${dbg_port}${path}")"
        done <<< "$ROUTE_PATHS"
        while IFS= read -r path; do
            [ -z "$path" ] && continue
            echo "  WS  :${dbg_port}${path} -> $(ws_probe "http://localhost:${dbg_port}${path}")"
        done <<< "$WS_CANDIDATES"
    done
    echo "--- last 25 log lines ---"; tail -25 "$LOG" 2>/dev/null
fi

cleanup
echo ""
echo "Compile: $(echo "$rewards" | jq '.compile'), Deploy: $(echo "$rewards" | jq '.deploy'), Health: $(echo "$rewards" | jq '.health')"
emit
