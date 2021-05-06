#!/bin/bash

cd "$(dirname "$0")"

GPIOPIN=22
TAGFILE="rfidtags.txt"
UNLOCKTIME="5s"

# Common path for all GPIO access
BASE_GPIO_PATH=/sys/class/gpio

# export GPIO pin so we can use it
if [ ! -e $BASE_GPIO_PATH/gpio$GPIOPIN ]; then
        echo "$GPIOPIN" > $BASE_GPIO_PATH/export
fi

#set GPIO pin direction to output
echo "out" > $BASE_GPIO_PATH/gpio$GPIOPIN/direction

echo "Waiting for tag..."
./wiegand_rpi |

while read -r tag; do
        
        echo "Read tag: $tag"

        isValid=$(grep -c "$tag" $TAGFILE)
        echo "$isValid"
        
        if [ "$isValid" -eq 1 ]; then
                #valid tag - trigger door unlock or light LED
                echo "Speak friend and enter!"
                echo "1" > "$BASE_GPIO_PATH/gpio$GPIOPIN/value"
                # send unlock signal for the specifiec time
                sleep $UNLOCKTIME
                # stop sending unlock signal
                echo "0" > "$BASE_GPIO_PATH/gpio$GPIOPIN/value"
        else
                echo "YOU SHALL NOT PASS!"
        fi
done

