from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

FRAMEWORKS = ("jakarta", "quarkus", "spring")

FRAMEWORK_DISPLAY = {
    "jakarta": "Jakarta EE",
    "quarkus": "Quarkus",
    "spring": "Spring",
}

# Tasks that need more than the default 4096 MB due to heavy build-time memory
# usage (e.g. Quarkus augmentation OOM on IBM Semeru JDK).
# Key = app_name, value = memory_mb override.
MEMORY_MB_OVERRIDES: dict[str, int] = {
    "producermethods": 6144,
}

# The <settings> namespace/schemaLocation attributes are deliberately omitted:
# they are optional, and spring-petclinic's `nohttp` build check (the only pom
# in the benchmark that runs it) fails on ANY http:// string -- including the
# settings.xsd namespace URIs -- so declaring them here breaks that oracle at
# compile time. The only URL below is the https mirror. (Matches the
# scarfbench-cli oracle_check_failing.py SETTINGS_XML.)
SETTINGS_XML = """\
<settings>
  <mirrors>
    <mirror>
      <id>google-maven-central</id>
      <name>Google Maven Central Mirror</name>
      <url>https://maven-central.storage-download.googleapis.com/maven2/</url>
      <mirrorOf>central</mirrorOf>
    </mirror>
  </mirrors>
</settings>
"""

# Framework-specific guidance appended to the instruction based on the target.
FRAMEWORK_SPECIFIC = {
    "jakarta": """\
## Jakarta EE (Open Liberty) Requirements

The target runtime is **Open Liberty**. The verifier runs `mvn liberty:run` inside
the container, so your project **must** include the Liberty Maven plugin and
server configuration:

1. **pom.xml** — Add the `liberty-maven-plugin`.
   If the app uses an embedded database (e.g. H2), configure
   `<copyDependencies>` in the plugin so the driver JAR is available to
   Liberty at runtime.

2. **server.xml** — Create `src/main/liberty/config/server.xml`.

3. **Packaging** — Use `<packaging>war</packaging>`. The app will be deployed
   as a WAR inside the Liberty server.

4. **Port** — Configure the HTTP port in `server.xml` (`httpPort`). The
   default Liberty port is 9080, but check the reference app's configuration
   for the expected port.
""",
    "quarkus": """\
## Quarkus Requirements

1. **pom.xml** — Use the Quarkus platform BOM and `quarkus-maven-plugin`.

2. **Packaging** — Use `<packaging>jar</packaging>`. Quarkus builds an
   uber-jar, not a WAR.

3. **Configuration** — Use `src/main/resources/application.properties` for
   Quarkus-style config (`quarkus.http.port`, `quarkus.datasource.jdbc.url`,
   `quarkus.hibernate-orm.database.generation`, etc.).

4. **Port** — Configure `quarkus.http.port` in `application.properties`.
   The default is 8080, but check the reference app's configuration for the
   expected port.
""",
    "spring": """\
## Spring Boot Requirements

1. **pom.xml** — Use `spring-boot-starter-parent` and the
   `spring-boot-maven-plugin`.

2. **Packaging** — Use `<packaging>jar</packaging>`. Spring Boot builds an
   executable fat JAR.

3. **Configuration** — Use `src/main/resources/application.properties` for
   Spring-style config (`server.port`, `spring.datasource.url`,
   `spring.jpa.hibernate.ddl-auto`, etc.).

4. **Port** — Configure `server.port` in `application.properties`. The
   default is 8080, but check the reference app's configuration for the
   expected port.
""",
}


@dataclass
class ScarfBenchCompileItem:
    task_id: str
    app_name: str
    layer: str
    framework_from: str
    framework_to: str
    source_dir: Path
    target_dir: Path


class ScarfBenchCompileAdapter:
    """Converts ScarfBench items into Harbor task directories (compile + deploy + health).

    Same task layout, toolchain image, and docker-free separate verifier as the
    ``scarfbench`` adapter, minus the per-app smoke suite: after compile and
    deploy, the verifier runs a generic HTTP health probe instead.

    Expected output structure per task:
      <output_dir>/<task_id>/
        - task.toml
        - instruction.md
        - environment/Dockerfile          (agent toolchain: Maven/JDK/Python/uv/Playwright)
        - environment/docker-compose.yaml
        - environment/settings.xml
        - environment/app/                (source framework code the agent converts)
        - solution/solve.sh               (oracle: applies the reference migration)
        - solution/app/                   (target framework reference code)
        - tests/test.sh                   (verifier: docker-free compile+deploy+health)
        - tests/framework.sh              (target-framework build/run logic)
        - tests/health_check.sh           (upstream health check, if available)
        - tests/settings.xml
    """

    def __init__(
        self,
        output_dir: Path,
        benchmark_dir: Path,
        templates_dir: Optional[Path] = None,
        docker_image: Optional[str] = None,
        task_image_repo: Optional[str] = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.benchmark_dir = Path(benchmark_dir)
        self.templates_dir = (
            templates_dir if templates_dir else Path(__file__).parent / "task-template"
        )
        # Pre-built toolchain image URL.  When provided, task.toml gets a
        # docker_image = "..." entry so Harbor pulls the image instead of
        # rebuilding it for every task run.  Leave None (or empty string) to
        # omit the field and fall back to the local Dockerfile.
        self.docker_image: Optional[str] = docker_image or None
        # Per-task image repo.  The toolchain image has an empty /app, and
        # Harbor skips environment/Dockerfile (and its `COPY app/ /app/`)
        # whenever task.toml sets docker_image, so the agent would see no
        # source.  When set, task.toml points at "<repo>:<task_id>", a thin
        # image built FROM the toolchain image with the task's app/ baked in
        # (see docker/build-and-push-tasks.sh).  The verifier image still
        # uses the plain toolchain image.
        self.task_image_repo: Optional[str] = task_image_repo or None
        self.items: Dict[str, ScarfBenchCompileItem] = self._discover_items()

    def list_available_tasks(self) -> List[str]:
        return list(self.items.keys())

    def get_task_info(self, task_id: str) -> Dict:
        item = self.items.get(task_id)
        if not item:
            return {}
        return {
            "task_id": item.task_id,
            "app_name": item.app_name,
            "layer": item.layer,
            "framework_from": item.framework_from,
            "framework_to": item.framework_to,
        }

    def run(
        self,
        *,
        task_ids: List[str] | None = None,
        limit: int | None = None,
        overwrite: bool = False,
    ) -> int:
        selected_ids = task_ids or self.list_available_tasks()
        if limit is not None:
            selected_ids = selected_ids[:limit]

        generated = 0
        for task_id in selected_ids:
            if (self.output_dir / task_id).exists() and not overwrite:
                continue
            try:
                self.generate_task(task_id)
                generated += 1
            except Exception as exc:
                logger.error("Failed to generate %s: %s", task_id, exc)
        return generated

    def generate_task(self, task_id: str) -> None:
        item = self.items.get(task_id)
        if not item:
            raise ValueError(f"Task {task_id} not found")

        task_root = self.output_dir / task_id
        env_dir = task_root / "environment"
        tests_dir = task_root / "tests"
        solution_dir = task_root / "solution"

        if task_root.exists():
            shutil.rmtree(task_root)

        env_dir.mkdir(parents=True, exist_ok=True)
        tests_dir.mkdir(parents=True, exist_ok=True)
        solution_dir.mkdir(parents=True, exist_ok=True)

        self._write_task_toml(item, task_root)
        self._write_instruction(item, task_root)
        if self._upload_mode:
            # Harbor uploads environment/ into the workdir only when there is
            # no Dockerfile or docker-compose.yaml, so ship just the source.
            self._copy_source_app(item, env_dir, flatten=True)
        else:
            self._copy_template("environment/Dockerfile", env_dir / "Dockerfile")
            self._copy_template(
                "environment/docker-compose.yaml", env_dir / "docker-compose.yaml"
            )
            self._write_settings_xml(env_dir / "settings.xml")
            self._copy_source_app(item, env_dir)
        self._write_solution(item, solution_dir)
        self._write_framework_sh(item, tests_dir)
        self._write_test_sh(tests_dir)
        self._copy_health_check(item, tests_dir)
        self._write_settings_xml(tests_dir / "settings.xml")
        self._write_verifier_dockerfile(tests_dir)

    def _discover_items(self) -> Dict[str, ScarfBenchCompileItem]:
        items: Dict[str, ScarfBenchCompileItem] = {}
        bench_dir = self.benchmark_dir / "benchmark"
        if not bench_dir.exists():
            raise FileNotFoundError(f"Benchmark directory not found: {bench_dir}")

        for layer_dir in sorted(bench_dir.iterdir()):
            if not layer_dir.is_dir():
                continue
            layer = layer_dir.name
            for app_dir in sorted(layer_dir.iterdir()):
                if not app_dir.is_dir():
                    continue
                app_name = app_dir.name
                available_frameworks = [
                    d.name
                    for d in app_dir.iterdir()
                    if d.is_dir() and d.name in FRAMEWORKS
                ]
                for fw_from in available_frameworks:
                    for fw_to in available_frameworks:
                        if fw_from == fw_to:
                            continue
                        task_id = f"{app_name}-{fw_from}-to-{fw_to}"
                        items[task_id] = ScarfBenchCompileItem(
                            task_id=task_id,
                            app_name=app_name,
                            layer=layer,
                            framework_from=fw_from,
                            framework_to=fw_to,
                            source_dir=app_dir / fw_from,
                            target_dir=app_dir / fw_to,
                        )
        return items

    def _copy_template(self, rel_path: str, dest: Path) -> None:
        src = self.templates_dir / rel_path
        if not src.exists():
            raise FileNotFoundError(f"Template not found: {src}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    def _read_template_text(self, rel_path: str) -> str:
        src = self.templates_dir / rel_path
        if not src.exists():
            raise FileNotFoundError(f"Template not found: {src}")
        return src.read_text(encoding="utf-8")

    def _write_task_toml(self, item: ScarfBenchCompileItem, task_root: Path) -> None:
        keywords = ", ".join(
            f'"{k}"'
            for k in [
                "scarfbench-compile",
                "migration",
                item.framework_from,
                item.framework_to,
                "java",
            ]
        )
        # Token substitution (not str.format) so the template's literal TOML
        # braces (e.g. authors = [{ name, email }]) survive verbatim.
        content = self._read_template_text("task.toml")
        replacements = {
            "__TASK_ID__": item.task_id,
            "__APP_NAME__": item.app_name,
            "__FRAMEWORK_FROM_DISPLAY__": FRAMEWORK_DISPLAY[item.framework_from],
            "__FRAMEWORK_TO_DISPLAY__": FRAMEWORK_DISPLAY[item.framework_to],
            "__KEYWORDS__": keywords,
            "__DOCKER_IMAGE__": self._agent_image(item.task_id) or "",
        }
        for token, value in replacements.items():
            content = content.replace(token, value)
        (task_root / "task.toml").write_text(content, encoding="utf-8")

    @property
    def _upload_mode(self) -> bool:
        """Prebuilt image, app delivered by Harbor's environment/ upload."""
        return bool(self.docker_image) and not self.task_image_repo

    def _agent_image(self, task_id: str) -> Optional[str]:
        if self.task_image_repo:
            return f"{self.task_image_repo}:{task_id}"
        return self.docker_image

    def _write_instruction(self, item: ScarfBenchCompileItem, task_root: Path) -> None:
        framework_specific = FRAMEWORK_SPECIFIC.get(item.framework_to, "")
        content = self._read_template_text("instruction.md")
        replacements = {
            "__FRAMEWORK_FROM__": FRAMEWORK_DISPLAY[item.framework_from],
            "__FRAMEWORK_TO__": FRAMEWORK_DISPLAY[item.framework_to],
            "__FRAMEWORK_SPECIFIC__": framework_specific,
        }
        for token, value in replacements.items():
            content = content.replace(token, value)
        (task_root / "instruction.md").write_text(content, encoding="utf-8")

    def _write_settings_xml(self, path: Path) -> None:
        path.write_text(SETTINGS_XML, encoding="utf-8")

    def _copy_source_app(
        self, item: ScarfBenchCompileItem, env_dir: Path, flatten: bool = False
    ) -> None:
        # flatten: app files go straight into environment/ because Harbor
        # uploads the contents of environment/ to the workdir (/app).
        app_dest = env_dir if flatten else env_dir / "app"
        src = item.source_dir
        if not src.exists():
            raise FileNotFoundError(f"Source directory not found: {src}")

        shutil.copytree(
            src,
            app_dest,
            ignore=shutil.ignore_patterns("target", ".m2repo"),
            dirs_exist_ok=flatten,
        )

        # Remove Dockerfile and test.sh from source copy — those belong to the
        # original benchmark harness, not the agent's working directory.
        # In flatten mode a root docker-compose.yaml would also make Harbor
        # skip the upload, so drop it too (variants like .yml are harmless).
        drop = ("Dockerfile", "test.sh") + (("docker-compose.yaml",) if flatten else ())
        for name in drop:
            p = app_dest / name
            if p.exists():
                p.unlink()

    def _write_verifier_dockerfile(self, tests_dir: Path) -> None:
        """Write tests/Dockerfile for the separate verifier container.

        Separate verifiers do not upload tests/ at runtime — the verifier image
        must already contain /tests. Base it on the pre-built toolchain image
        when available, otherwise on the agent Dockerfile minus the source app.
        """
        if self.docker_image:
            base = f"FROM {self.docker_image}\n"
        else:
            base = self._read_template_text("environment/Dockerfile").replace(
                "COPY app/ /app/\n", ""
            )
        (tests_dir / "Dockerfile").write_text(
            base + "\nCOPY . /tests/\nRUN chmod +x /tests/test.sh\n",
            encoding="utf-8",
        )

    def _write_framework_sh(self, item: ScarfBenchCompileItem, tests_dir: Path) -> None:
        """Copy the target framework's docker-free build/run logic.

        ``tests-{framework}/framework.sh`` defines SUCCESS/FAILURE patterns and
        the fw_prepare/fw_build/fw_run functions that ``tests/test.sh`` sources
        to compile, boot, and health-probe the app without a Docker daemon.
        """
        self._copy_template(
            f"tests-{item.framework_to}/framework.sh", tests_dir / "framework.sh"
        )

    def _write_test_sh(self, tests_dir: Path) -> None:
        tpl = self.templates_dir / "tests" / "test.sh"
        if not tpl.exists():
            raise FileNotFoundError(f"test.sh template not found: {tpl}")
        out = tests_dir / "test.sh"
        shutil.copy2(tpl, out)
        out.chmod(0o755)

    def _write_solution(self, item: ScarfBenchCompileItem, solution_dir: Path) -> None:
        """Write the oracle solution: the migrated reference app plus solve.sh.

        ScarfBench ships the target-framework migration alongside the source.
        The oracle copies that reference tree over ``/app`` so the verifier's
        compile + deploy + health check runs against a known-good migration.
        """
        target = item.target_dir
        if not target.exists():
            raise FileNotFoundError(f"Target (reference) directory not found: {target}")

        app_dest = solution_dir / "app"
        shutil.copytree(
            target, app_dest, ignore=shutil.ignore_patterns("target", ".m2repo")
        )
        # Drop benchmark-harness files — solve.sh deploys the app, the verifier
        # owns the Dockerfile/test.sh.
        for name in ("Dockerfile", "test.sh"):
            p = app_dest / name
            if p.exists():
                p.unlink()

        out = solution_dir / "solve.sh"
        self._copy_template("solution/solve.sh", out)
        out.chmod(0o755)

    def _copy_health_check(self, item: ScarfBenchCompileItem, tests_dir: Path) -> None:
        """Copy the target framework's test.sh from the benchmark repo.

        The upstream test.sh contains the exact health check URL and path
        for each app+framework combination (e.g. /petclinic/home.jsf for
        Jakarta petclinic, /api/tags for realworld, port 9080 for Jakarta, etc.).
        test.sh runs it against each candidate port as the first health probe.
        """
        src = item.target_dir / "test.sh"
        if not src.exists():
            logger.warning(
                "No test.sh found in %s — health check will use generic fallback",
                item.target_dir,
            )
            return
        out = tests_dir / "health_check.sh"
        shutil.copy2(src, out)
        out.chmod(0o755)
