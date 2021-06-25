#!/usr/bin/env python3

import io
import json
import subprocess
import os
import time
import sys


# from gpiozero import LED

from dotenv import load_dotenv
import requests

load_dotenv()

GLUE_ENDPOINT = "https://glue.peach.evangoo.de"
GLUE_TOKEN = os.getenv("RFID_TOKEN")

FOB_CACHE_PATH = "authorized-fob-cache.json"

headers = {"Authorization": f"Bearer {GLUE_TOKEN}"}


class DummyLED:
    def __init__(self, pin):
        pass

    def on(self):
        pass

    def off(self):
        pass


# output = LED(22)
output = DummyLED(22)
output.off()

proc = subprocess.Popen(["./wiegand_rpi"], stdout=subprocess.PIPE)

try:
    with open(FOB_CACHE_PATH) as authorized_fobs_fp:
        authorized_fobs = frozenset(json.load(authorized_fobs_fp))
except (FileNotFoundError, json.JSONDecodeError):
    authorized_fobs = []

for line in io.TextIOWrapper(proc.stdout, encoding="utf-8"):
    fob = line.rstrip()
    try:
        auth_res = requests.get(
            f"{GLUE_ENDPOINT}/rfid/auth",
            params={"fob": fob},
            headers=headers,
            timeout=1,
        )
        auth_res.raise_for_status()
        if auth_res.json().get("authorized_fobs", None) is None:
            raise ValueError("Server doesn't know authorized fobs!")
        new_authorized_fobs = frozenset(auth_res.json()["authorized_fobs"])
    except (
        requests.HTTPError,
        requests.exceptions.ReadTimeout,
        KeyError,
        ValueError,
    ) as error:
        print(error, file=sys.stderr)
        new_authorized_fobs = authorized_fobs
    if fob in new_authorized_fobs:
        print(f"Unlocking for fob {fob}")
        output.on()
        time.sleep(5)
        output.off()
    else:
        print(f"Fob {fob} is unauthorized!")
    if authorized_fobs != new_authorized_fobs:
        with open(FOB_CACHE_PATH, "w") as authorized_fobs_fp:
            json.dump(list(new_authorized_fobs), authorized_fobs_fp)
    authorized_fobs = new_authorized_fobs
