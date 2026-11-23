"""The 50-task parity subset (``--split parity``).

Drawn at random from the 212 Harbor task ids sorted by name:
``random.Random(0).sample(ids, 20)``, then ``random.Random(1).sample(rest, 30)``
over the remaining 192 ids (the first 20 were the initial parity sample; the
other 30 extended it to 50). ``draw_parity_subset`` reproduces the list, which
is kept here explicitly so the subset does not depend on the RNG.
"""

import random

PARITY_TASK_IDS = (
    "agavemonocot-seed0",
    "armchair-seed0",
    "bananamonocot-seed0",
    "basketbase-seed0",
    "bathroomsink-seed0",
    "bedframe-seed0",
    "bookcolumn-seed0",
    "braincoral-seed0",
    "bush-seed0",
    "cabinet-seed0",
    "can-seed0",
    "cauliflowercoral-seed0",
    "ceilinglight-seed0",
    "diffgrowthbasecoral-seed0",
    "doorcasing-seed0",
    "fern-seed0",
    "flowerplant-seed0",
    "fork-seed0",
    "fruitblackberry-seed0",
    "fruitcoconuthairy-seed0",
    "fruitpineapple-seed0",
    "honeycombcoral-seed0",
    "jellyfish-seed0",
    "largeshelf-seed0",
    "leafheart-seed0",
    "leafpine-seed0",
    "leafv2-seed0",
    "lichen-seed0",
    "moss-seed0",
    "mushroom-seed0",
    "mushroomgrowth-seed0",
    "natureshelftrinkets-seed0",
    "nautilus-seed0",
    "numleafgrass-seed0",
    "oven-seed0",
    "pants-seed0",
    "pineneedle-seed0",
    "plantcontainer-seed0",
    "prickypearcactus-seed0",
    "reedbranchmonocot-seed0",
    "rug-seed0",
    "sidetable-seed0",
    "snake-seed0",
    "spatulabase-seed0",
    "tablecoral-seed0",
    "truncatedtree-seed0",
    "tubecoral-seed0",
    "tvstand-seed0",
    "ushapedstaircase-seed0",
    "veratrumbranchmonocot-seed0",
)


def draw_parity_subset(task_ids: list[str]) -> list[str]:
    """Re-draw the subset from all 212 task ids (for checking PARITY_TASK_IDS)."""
    ids = sorted(task_ids)
    first = random.Random(0).sample(ids, 20)
    taken = set(first)
    rest = [i for i in ids if i not in taken]
    return sorted(first + random.Random(1).sample(rest, 30))
