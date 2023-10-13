import os

import iagon
from dotenv import load_dotenv

load_dotenv()

seed_phrase = os.environ["SEED"]

with iagon.IagonAdapter.session(seed_phrase) as session:
    with open("minswap_catalyst_groups.zip", "rb") as fr:
        file_id = session.upload(
            "minswap_catalyst_groups.zip",
            fr.read(),
            private=False,
        )

    print(file_id)
