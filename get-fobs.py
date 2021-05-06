#!/usr/bin/env python3
# this is the latest version as of Sunday, April 3, 2021
import os
import datetime
from typing import Any, Dict, List, Generator, Tuple
import sys

import requests
# to do: make cronjob to establish API key value regularly from outside the program
API_KEY = os.getenv("NEONCRM_API_KEY")
ORG_ID = "decaturmakers"
AUTH = (ORG_ID, API_KEY)
FOB_FIELD_NAME = "Fob10Digit"
FOB_FIELD_ID = 79

MAX_PAGE_SIZE = 200

API_ENDPOINT = "https://api.neoncrm.com/v2"

session = requests.session()

today = datetime.datetime.now().strftime("%Y-%m-%d")

def gen_active_fobs() -> Generator[str, None, None]:
    def get_page(page: int) -> Tuple[int, List[Dict[str, Any]]]:
        search_res = session.post(
            f"{API_ENDPOINT}/accounts/search",
            auth=AUTH,
            json={
                "outputFields": [
                    "Full Name (F)",
                    "Membership Expiration Date",
                    FOB_FIELD_ID,
                ],
                "pagination": {
                    "currentPage": page,
                    "pageSize": MAX_PAGE_SIZE,
                },
                "searchFields": [
                    {
                        "field": "Membership Expiration Date",
                        "operator": "GREATER_AND_EQUAL",
                        "value": today,
                    }
                ],
            },
        )
        search_res.raise_for_status()
        search_dict = search_res.json()

        last_page = search_dict["pagination"]["totalPages"] - 1
        results = search_dict["searchResults"]

        return last_page, results

    current_page = 0
    last_page = 0

    while current_page <= last_page:
        last_page, results = get_page(current_page)
        for result in results:
            fob_id = result[FOB_FIELD_NAME]
            if fob_id:
                print(result, file=sys.stderr)
                yield fob_id
        current_page += 1

fob_count = 0
for fob in gen_active_fobs():
    print(fob)
    fob_count += 1
print(f"Found {fob_count} active fobs", file=sys.stderr)
