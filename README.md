The front (East) door to Decatur Makers makerspace can be opened by active members with their RFID fob. These fobs are read by an ERK871 RFID reader, which sends both serial and Wiegand style data. We use 26 bit Wiegand fobs as of May, 2021.

![ERK871 Wiegand Reader](/images/WiegandReader.png?raw=true)

The reader is powered by a 120V/24V power supply, which is connected to a custom circuit board that:
- sends 24V to the door motor
- sends 12V to the ERK871
- receives both a 3V supply (tonic, over pin 1) and a 3V control signal (on pin 22) from a Raspberry Pi Zero W

![120V/12V Power Supply](/images/PowerSupply.jpg?raw=true)

The Raspberry Pi Zero W sends 3V over GPIO pin 1 to both the low voltage side of a logic level converter (to step down the 5V Wiegand data), and to the power supply circuit described above. It also sends 5V over GPIO pin 2 to the high voltage side of the logic level converter.

The Raspberry Pi Zero W receives Weigand data (data0 and data 1) stepped down via the Logic Level Converter to 3V from 5V on GPIO pins 17 and 18. Note that these are numbered 0 and 1 in the WiringPi standard, which is implemented in wiegand_rpi via the WiringPi library. Do not connect Wiegand data sources directly to the raspberry pi as they run at 5V and will damage the Raspberry Pi. Pin 3 is the common ground for the 12V power supply, the RFID reader, and the Raspberry Pi (and its 5V power supply provided by a 12V/5V stepper)

![Raspberry Pi Wiring](/images/RaspberryPiWIring.png?raw=true)

When a fob is passed near the reader, wiegand_rpi interprets the 26 bit fob data and sends the digital "full code" of the fob, a 10-digit number with three leading zeroes, to stdout.

# `rfidclient`

`rfidclient` is a daemon written in Python that will start on boot and runs `wiegand_rpi`, waiting for this 10-digit number. It makes an HTTPS request to our "glue" server to check whether the fob number is valid, and if it is, sends 3V over GPIO pin 22 to the control input on the custom circuit board described above -- this closes the relay sending 24V to the door motor. The signal stays on for 5 sec.

The code for the back-end "glue" server is at https://github.com/DecaturMakers/glue/ (currently a private repo).

## Compiling `wiegand_rpi`

A compiled `wiegand_rpi` binary is included in this repo at `rfidclient/wiegand_rpi`. Here's how to compile a new one if changes need to be made. It's probably easiest to do this on a physical Raspberry Pi.

Download and install the wiringpi ``.deb`` from the latest release at https://github.com/WiringPi/WiringPi/releases

Compile:

```
gcc wiegand_rpi.c -lwiringPi -lpthread -lrt  -Wall -o rfidclient/wiegand_rpi -O
```

## Installing

If you did not compile on the same machine, first download the ``.deb`` package from the latest release at https://github.com/WiringPi/WiringPi/releases and install it.

Run the install script:

```
sudo make install
```

Then, fill out `/etc/default/rfidclient` with the https:// address of the glue server and an authorization token.

The installation script will `enable` the `rfidclient` service so it starts at boot. To start the service immediately, run:

```
sudo systemctl start rfidclient.service
```
