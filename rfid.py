#!/usr/bin/env python3

import importlib.resources as package_resources
import io
import json
import os
import subprocess
import sys
import time


try:
    from gpiozero import LED
except ImportError:
    print("Error importing gpiozero! Using stub.", file=sys.stderr)
    LED = None

from dotenv import load_dotenv
import requests

load_dotenv()

GLUE_ENDPOINT = "https://glue.peach.evangoo.de"
GLUE_TOKEN = os.getenv("RFID_TOKEN")

FOB_CACHE_PATH = "authorized-fob-cache.json"

headers = {"Authorization": f"Bearer {GLUE_TOKEN}"}


if LED is None:
    class LED:
        def __init__(self, pin):
            pass

        def on(self):
            pass

        def off(self):
            pass


output = LED(22)
# output = DummyLED(22)
output.off()

proc = subprocess.Popen(["./wiegand_rpi"], stdout=subprocess.PIPE)

try:
    with open(FOB_CACHE_PATH) as authorized_fobs_fp:
        authorized_fobs = frozenset(json.load(authorized_fobs_fp))
except (FileNotFoundError, json.JSONDecodeError):
    authorized_fobs = frozenset()

for line in io.TextIOWrapper(proc.stdout, encoding="utf-8"):
    fob = line.strip().zfill(10)
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
