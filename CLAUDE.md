# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Raspberry Pi-based RFID door access control system for Decatur Makers makerspace. Reads 26-bit Wiegand fobs via an ERK871 RFID reader, authenticates against a remote "glue" server, and controls an electric strike/latch via GPIO.

## Architecture

Two cooperating processes, managed by systemd:

1. **`rfidclient`** (Python) — Main daemon. Spawns the `wiegand_rpi` C binary as a subprocess, reads fob codes from its stdout, authenticates against the glue server, and drives a GPIO output pin to unlock the door. Also supports SIGUSR1 to trigger an unlock externally. Uses a background thread (`scan_worker`) for auth + unlock so the main loop can keep reading fobs.

2. **`rfid-prometheus`** (Python) — Separate process that reads door state from POSIX shared memory (`doorstateshm`) written by rfidclient, and exposes Prometheus metrics on port 8080.

**Shared memory IPC:** `DoorState` (`rfidclient/doorstate.py`) is a struct-packed blob shared between the two processes via `multiprocessing.SharedMemory`. It tracks process uptime, door open/closed state, and scan counts.

**`wiegand_rpi`** (C) — Interrupt-driven Wiegand protocol reader using wiringPi. Outputs the numeric fob code to stdout when a valid 26-bit sequence is read. Pre-compiled binaries for armhf and aarch64 are shipped inside the `rfidclient` package.

## Build & Install

```bash
# Install on a Raspberry Pi (installs Python package + systemd units)
sudo make install

# Compile wiegand_rpi C binary (requires wiringPi .deb from https://github.com/WiringPi/WiringPi/releases)
gcc wiegand_rpi.c -lwiringPi -lpthread -lrt -Wall -o rfidclient/wiegand_rpi -O
```

There are no tests, no linter configuration, and no CI pipeline.

## Configuration

Environment variables in `/etc/default/rfidclient` (loaded via python-dotenv). See `example.env` for all options. Required: `GLUE_ENDPOINT`, `GLUE_TOKEN`, `ZONE`.

## Key Details

- Python package uses `setuptools` with `setup.py` (no pyproject.toml).
- Entry points: `rfidclient=rfidclient.rfidclient:main`, `rfid-prometheus=rfidclient.prometheus_client:main`.
- The correct `wiegand_rpi` binary variant (armhf vs aarch64) is selected at runtime based on `platform.machine()`.
- Authorized fob list is cached locally at `~/.cache/rfidclient/authorized-fob-cache.json` for offline resilience.
- GPIO uses `gpiozero` with a `DummyLED` fallback when gpiozero is unavailable (e.g., dev machines).
- Production deployment is managed via Puppet.
