#!/usr/bin/env python3

import importlib.resources as package_resources
import io
import json
import logging
import os
import subprocess
import sys
import time

from dotenv import load_dotenv
import requests

logging.basicConfig(level=logging.DEBUG)

try:
    import gpiozero
    output = gpiozero.LED(22)
except (ImportError, gpiozero.exc.BadPinFactory):
    print("gpiozero error! Using stub.", file=sys.stderr)
    class DummyLED:
            def __init__(self, pin):
                pass

            def on(self):
                pass

            def off(self):
                pass
    output = DummyLED(22)

output.off()

load_dotenv(dotenv_path="/etc/default/rfidclient")

GLUE_ENDPOINT = os.getenv("GLUE_ENDPOINT")
GLUE_TOKEN = os.getenv("GLUE_TOKEN")

FOB_CACHE_PATH = os.path.expanduser("~/.cache/rfidclient/authorized-fob-cache.json")
os.makedirs(os.path.dirname(FOB_CACHE_PATH), exist_ok=True)

headers = {"Authorization": f"Bearer {GLUE_TOKEN}"}

def main():
    with package_resources.path("rfidclient", "wiegand_rpi") as proc_path:
        proc = subprocess.Popen([proc_path], stdout=subprocess.PIPE)

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
        except Exception as e:
            logging.exception("Couldn't get authorized fobs.")
            new_authorized_fobs = authorized_fobs
        if fob in new_authorized_fobs:
            logging.info(f"Unlocking for fob {fob}")
            output.on()
            time.sleep(5)
            output.off()
        else:
            logging.info(f"Fob {fob} is unauthorized!")
        if authorized_fobs != new_authorized_fobs:
            with open(FOB_CACHE_PATH, "w") as authorized_fobs_fp:
                json.dump(list(new_authorized_fobs), authorized_fobs_fp)
        authorized_fobs = new_authorized_fobs

if __name__ == "__main__":
    main()
