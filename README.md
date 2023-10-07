# Decatur Makers Raspberry Pi RFID Wiegand Reader

The front (East) and side (welding pad / South) doors to Decatur Makers makerspace can be opened by active members with their RFID fob. These fobs are read by an ERK871 RFID reader, which sends both serial and Wiegand style data. We use 26 bit Wiegand fobs and read the Wiegand data/

Each door uses drastically different hardware aside from the RFID readers, but the same software (from this repository).

## Hardware

* [Version 1](hardware_v1.md) - Front (East) door - 24V SDC LR100SGK latch retractor on a Sargent 20-series exit device (push bar)
* [Version 2](hardware_v2.md) - Side (South / welding pad) door - 12V [HES 9600 630LBM](https://www.hesinnovations.com/en/products/electric-strikes/9600-series) electric strike used with a [LSDA PD9000 ](https://www.lsda.com/lsda-product/lsda-exit-device-panic-36-rim/) rim exit device

## `rfidclient` Daemon

`rfidclient` is a daemon written in Python that will start on boot and runs `wiegand_rpi`, waiting for this 10-digit number. It makes an HTTPS request to our "glue" server to check whether the fob number is valid, and if it is, sends 3V over GPIO pin 22 to the control input on the custom circuit board described above -- this closes the relay sending 24V to the door motor. The signal stays on for 5 sec.

The code for the back-end "glue" server is at https://github.com/DecaturMakers/glue/ (currently a private repo).

## `wiegand_rpi` binary

When a fob is passed near the reader, wiegand_rpi interprets the 26 bit fob data and sends the digital "full code" of the fob, a 10-digit number with three leading zeroes, to stdout.

### Compiling `wiegand_rpi`

A compiled `wiegand_rpi` binary is included in this repo at `rfidclient/wiegand_rpi`. Here's how to compile a new one if changes need to be made. It's probably easiest to do this on a physical Raspberry Pi.

Download and install the wiringpi ``.deb`` from the latest release at https://github.com/WiringPi/WiringPi/releases

Compile:

```
gcc wiegand_rpi.c -lwiringPi -lpthread -lrt  -Wall -o rfidclient/wiegand_rpi -O
```

## `rfid-prometheus` Daemon

The `rfidclient` Daemon exposes a shared memory (shm) structure (see [rfidclient/doorstate.py](rfidclient/doorstate.py)) with information about how long the process has been running, the number of authorized and unauthorized fob scans since start, and (if a latch contact pin is defined) the current state of the latch contact as well as the timestamps when it was last opened and closed. This information is exposed in a [Prometheus](https://prometheus.io/)-compatible format on port 8080.

## Installing

If you did not compile on the same machine, first download the ``.deb`` package from the latest release at https://github.com/WiringPi/WiringPi/releases and install it.

Run the install script:

```
sudo make install
```

Then, fill out `/etc/default/rfidclient` with the https:// address of the glue server (a Decatur Makers-specific custom authorization server) and an authorization token.

The installation script will `enable` the `rfidclient` service so it starts at boot. To start the service immediately, run:

```
sudo systemctl start rfidclient.service
```

**Note:** At Decatur Makers, installation and configuration is currently managed via Puppet.

## Configuration

**Note:** At Decatur Makers, installation and configuration is currently managed via Puppet.

This project is configured via environment variables set in ``/etc/default/rfidclient`` and loaded via [dotenv](https://pypi.org/project/dotenv/). The currently-supported configuration options are as follows:

* `GLUE_ENDPOINT` str *required* - endpoint URL for the glue server.
* `GLUE_TOKEN` str *required* - auth token for the glue server.
* `ZONE` str *required* - Zone (door) name; used by the glue server and prometheus client.
* `OUTPUT_PIN` int *optional; default: 22* - Output pin number to use for the strike/latch output; normally low, high when opening door.
* `CONTACT_PIN` int *optional; default 0 means not used* - Input pin number for latch position sensor, to determine if latch is currently open or closed. This pin should be normally closed, i.e. giving a value of 1 when the door is closed.
* `CONTACT_TIMEOUT_MS` int *optional default 0* - Only valid if `CONTACT_PIN` is non-zero: how long (in ms) to keep latch/strike open after `CONTACT_PIN` turns off, before re-locking.
