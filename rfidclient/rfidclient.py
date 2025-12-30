#!/usr/bin/env python3

import threading
import importlib.resources as package_resources
import io
import json
import logging
import os
import signal
import subprocess
import sys
import time
import platform
from typing import NoReturn, Optional
from signal import pause
from multiprocessing.shared_memory import SharedMemory

import timeout_decorator
from dotenv import load_dotenv
import requests
from rfidclient.doorstate import DoorState

AUTH_TIMEOUT = 2
DOOR_OPEN_SECONDS = 10

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s:%(name)s:%(message)s'
)

load_dotenv(dotenv_path="/etc/default/rfidclient")

GLUE_ENDPOINT: str = os.getenv("GLUE_ENDPOINT")
GLUE_TOKEN: str = os.getenv("GLUE_TOKEN")
ZONE: str = os.getenv("ZONE")
OUTPUT_PIN: int = int(os.getenv("OUTPUT_PIN", "22"))
CONTACT_PIN: int = int(os.getenv("CONTACT_PIN", "0"))
CONTACT_TIMEOUT_MS: int = int(os.getenv("CONTACT_TIMEOUT_MS", "0"))
CONTACT_SLEEP_TIME = CONTACT_TIMEOUT_MS / 1000.0
# NOTE: Contact pin should be normally closed (i.e. when door is closed, contact is closed, pin value is 1)


class DummyLED:
    def __init__(self, pin):
        pass

    def on(self):
        pass

    def off(self):
        pass


try:
    import gpiozero
    output = gpiozero.LED(OUTPUT_PIN)
    logging.info('Controlling strike output on pin %s', OUTPUT_PIN)
    if CONTACT_PIN > 0:
        door_contact = gpiozero.Button(
            CONTACT_PIN, pull_up=True, bounce_time=0.1
        )
        logging.info('Reading door contact on pin %s', CONTACT_PIN)
    else:
        door_contact = DummyLED(CONTACT_PIN)
except (ImportError, gpiozero.exc.BadPinFactory):
    print("gpiozero error! Using stub.", file=sys.stderr)
    output = DummyLED(OUTPUT_PIN)
    door_contact = DummyLED(CONTACT_PIN)

output.off()

FOB_CACHE_PATH = os.path.expanduser("~/.cache/rfidclient/authorized-fob-cache.json")
os.makedirs(os.path.dirname(FOB_CACHE_PATH), exist_ok=True)

door_state: DoorState = DoorState()
shm: SharedMemory = SharedMemory(
    name='doorstateshm', create=True, size=DoorState.STRUCT_SIZE
)

headers = {"Authorization": f"Bearer {GLUE_TOKEN}"}

try:
    with open(FOB_CACHE_PATH) as authorized_fobs_fp:
        authorized_fobs = frozenset(json.load(authorized_fobs_fp))
except (FileNotFoundError, json.JSONDecodeError):
    authorized_fobs = frozenset()

new_scanned_fob = threading.Condition()
scanned_fob: Optional[str] = None


@timeout_decorator.timeout(AUTH_TIMEOUT, use_signals=False)
def get_auth_res(fob):
    return requests.get(
        f"{GLUE_ENDPOINT}/rfid/auth",
        params={"fob": fob, "zone": ZONE},
        headers=headers,
    )


def unlock_door(reason: str = "fob"):
    """Unlock the door by energizing the strike/latch output.

    Args:
        reason: The reason for unlocking (e.g., "fob", "signal")
    """
    logging.info("Unlocking door (reason: %s)", reason)
    door_state.set_scan_authorized(shm)
    output.on()
    time.sleep(DOOR_OPEN_SECONDS)
    logging.debug('Relocking door')
    output.off()
    logging.debug('Door relocked')


def scan_worker() -> NoReturn:
    global authorized_fobs
    while True:
        try:
            with new_scanned_fob:
                new_scanned_fob.wait()
            fob = scanned_fob
            try:
                auth_res = get_auth_res(fob)
                auth_res.raise_for_status()
                if auth_res.json().get("authorized_fobs", None) is None:
                    logging.critical("Server doesn't know authorized fobs!")
                    raise ValueError("Server doesn't know authorized fobs!")
                new_authorized_fobs = frozenset(auth_res.json()["authorized_fobs"])
                if authorized_fobs != new_authorized_fobs:
                    with open(FOB_CACHE_PATH, "w") as authorized_fobs_fp:
                        json.dump(list(new_authorized_fobs), authorized_fobs_fp)
            except Exception as e:
                logging.exception("Couldn't get authorized fobs.")
                new_authorized_fobs = authorized_fobs
            if fob in new_authorized_fobs:
                logging.info("Unlocking for fob %s", fob)
                unlock_door("fob")
            else:
                logging.info("Fob %s is unauthorized!", fob)
                door_state.set_scan_unauthorized(shm)
            authorized_fobs = new_authorized_fobs
        except Exception as e:
            logging.exception("")


def door_opened() -> NoReturn:
    logging.info("Door contact / latch sensor opened")
    door_state.set_door_open(shm)
    if output.value and CONTACT_TIMEOUT_MS:
        time.sleep(CONTACT_SLEEP_TIME)
        logging.debug('Relocking door (latch sensor')
        output.off()
        logging.debug('Door relocked (latch sensor)')


def door_closed() -> NoReturn:
    door_state.set_door_closed(shm)
    logging.info("Door contact / latch sensor closed")


def door_contact_handler() -> NoReturn:
    logging.info(
        "Starting door_contact_handler thread; door_contact value is %s",
        door_contact.value
    )
    door_contact.when_pressed = door_closed
    door_contact.when_released = door_opened
    pause()


def signal_unlock_handler(signum, frame):
    """Signal handler to trigger door unlock via SIGUSR1."""
    logging.info("Received unlock signal (SIGUSR1)")
    unlock_door("signal")


threading.Thread(target=scan_worker, daemon=True).start()

if CONTACT_PIN > 0:
    if door_contact.is_pressed:
        door_state.set_door_closed(shm)
    else:
        door_state.set_door_open(shm)
    threading.Thread(target=door_contact_handler, daemon=True).start()


def main():
    global scanned_fob

    # Register signal handler for remote unlock trigger
    signal.signal(signal.SIGUSR1, signal_unlock_handler)
    logging.info("Registered SIGUSR1 handler for remote unlock")

    bin_name = "wiegand_rpi"
    if platform.machine() == "aarch64":
        bin_name = "wiegand_rpi_arm64"
    with package_resources.path("rfidclient", bin_name) as proc_path:
        proc = subprocess.Popen([proc_path], stdout=subprocess.PIPE)

    logging.info("Listening for fobs...")

    for line in io.TextIOWrapper(proc.stdout, encoding="utf-8"):
        scanned_fob = line.strip().zfill(10)
        with new_scanned_fob:
            new_scanned_fob.notify_all()


if __name__ == "__main__":
    main()
