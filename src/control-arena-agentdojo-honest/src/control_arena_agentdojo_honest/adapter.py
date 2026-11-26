import inspect
import json
import shutil
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory

from agentdojo.default_suites.v1.tools import travel_booking_client as travel
from agentdojo.task_suite.load_suites import get_suite

TEMPLATE = Path(__file__).with_name("task-template")
RESTAURANT_LOOKUPS = (
    travel.get_all_restaurants_in_city, travel.get_cuisine_type_for_restaurants,
    travel.check_restaurant_opening_hours, travel.get_rating_reviews_for_restaurants,
    travel.get_restaurants_address, travel.get_price_for_restaurants,
)
CAR_LOOKUPS = (
    travel.get_all_car_rental_companies_in_city, travel.get_car_types_available,
    travel.get_car_fuel_options, travel.get_rating_reviews_for_car_rental,
    travel.get_car_price_per_day,
)
CASES = {"travel-user-task-9": 9, "travel-user-task-10": 10, "travel-user-task-13": 13, "travel-user-task-14": 14}


def write(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def write_lookups(directory: Path, environment, number: int) -> None:
    # Only the public fields consumed by the selected, read-only source functions leave the suite.
    if number in (9, 10):
        functions = RESTAURANT_LOOKUPS
        records = environment.restaurants.restaurant_list
        city, field = "Paris", "restaurant_list"
        columns = {"name", "city", "address", "cuisine_type", "operating_hours", "rating", "reviews", "price_per_person"}
    else:
        functions = CAR_LOOKUPS
        records = environment.car_rental.company_list
        city, field = "Los Angeles", "company_list"
        columns = {"name", "city", "car_types_available", "fuel_options", "rating", "reviews", "price_per_day"}
    projection = {field: [record.model_dump(mode="json", include=columns) for record in records if record.city == city]}
    write(directory / "inventory.json", json.dumps(projection, ensure_ascii=False))
    definitions = "\n\n".join(inspect.getsource(fn) for fn in functions)
    mapping = ",\n".join(f'    "{fn.__name__}": {fn.__name__}' for fn in functions)
    write(directory / "native_lookups.py", "from __future__ import annotations\n\n" + definitions + "\nTOOLS = {\n" + mapping + "\n}\n")
    pkg = distribution("agentdojo")
    license_file = next(f for f in pkg.files if str(f).endswith(".dist-info/licenses/LICENSE"))
    shutil.copyfile(pkg.locate_file(license_file), directory / "AGENTDOJO-LICENSE")


class ControlArenaAgentdojoHonestAdapter:
    def __init__(self, output_dir: Path, limit=None, overwrite=False, task_ids=None):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids

    def run(self) -> list[Path]:
        if self.limit is not None and self.limit < 0:
            raise ValueError("--limit must be nonnegative")
        wanted = set(CASES) if self.task_ids is None else {s.removeprefix("control-arena/") for s in self.task_ids}
        if unknown := wanted - CASES.keys():
            raise ValueError(f"Outside the read-only travel allowlist: {sorted(unknown)}")
        selected = [slug for slug in CASES if slug in wanted][:self.limit]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        suite = get_suite("v1.2.1", "travel")
        environment = suite.load_and_inject_default_environment({})
        paths = []
        for slug in selected:
            path = self.output_dir / slug
            if path.exists() and not self.overwrite:
                paths.append(path)
                continue
            number = CASES[slug]
            task = suite.get_user_task_by_id(f"user_task_{number}")
            with TemporaryDirectory(dir=self.output_dir) as temporary:
                staging = Path(temporary) / "new"
                shutil.copytree(TEMPLATE, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                config = staging / "task.toml"
                write(config, config.read_text("utf-8").replace("{slug}", slug))
                instructions = staging / "instruction.md"
                write(instructions, instructions.read_text("utf-8").replace("{prompt}", task.PROMPT))
                write_lookups(staging / "environment", environment, number)
                write(staging / "solution" / "answer.txt", task.GROUND_TRUTH_OUTPUT)
                write(staging / "tests" / "case.json", json.dumps({"user_task_id": task.ID}))
                for script in staging.rglob("*.sh"):
                    write(script, script.read_text("utf-8"))
                    script.chmod(0o755)
                previous = Path(temporary) / "previous"
                if path.exists():
                    path.rename(previous)
                try:
                    staging.rename(path)
                except OSError:
                    if previous.exists():
                        previous.rename(path)
                    raise
            paths.append(path)
        return paths
