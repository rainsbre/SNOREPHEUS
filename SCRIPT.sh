#!/bin/bash

#   _____                        _
#  / ____|                      | |
# | (___  _ __   ___  _ __ _ __ | |__   ___ _   _ ___
#  \___ \| '_ \ / _ \| '__| '_ \| '_ \ / _ \ | | / __|
#  ____) | | | | (_) | |  | |_) | | | |  __/ |_| \__ \
# |_____/|_| |_|\___/|_|  | .__/|_| |_|\___|\__,_|___/ COLLECTION SCRIPT
#                         | |
#                         |_|

echo "WELCOME TO SNORPHEUS"
echo "CHECKING FOR HUB CONNECTION"

# BNO055 I2C address and register addresses
BNO055_ADDR=0x28
EUL_H_LSB=0x1A
EUL_H_MSB=0x1B
EUL_R_LSB=0x1C
EUL_R_MSB=0x1D
EUL_P_LSB=0x1E
EUL_P_MSB=0x1F

# Wait for 15 minutes to see if we can establish a network connection
for ((i=1; i<=15; i++)); do
  if ping -q -c 1 -W 1 google.com >/dev/null; then
    echo "Connected to network, idling..."
    while true; do
      echo "IDLE"
      sleep 36000  # idle for 10 hours
    done
  fi
  echo "PING"
  sleep 15  # 15 seconds before trying again
done

# No connection was established within 15 minutes, execute the script normally
echo "CONNECTION NOT FOUND. BEGINNING DATA COLLECTION"

# BNO055 register addresses
OPR_MODE=0x3D
SYS_TRIGGER=0x3F

# Reset the sensor
i2cset -y 1 $BNO055_ADDR $SYS_TRIGGER 0x20
sleep 0.7  # Wait for the sensor to restart

# Set to CONFIG mode
i2cset -y 1 $BNO055_ADDR $OPR_MODE 0x00
sleep 0.05  # Wait for the sensor to switch mode

# Set to NDOF mode
i2cset -y 1 $BNO055_ADDR $OPR_MODE 0x0C
sleep 0.05  # Wait for the sensor to switch mode

# set threshold
THRESH=1000
echo "TRIGGER THRESHOLD IS $THRESH"

while true
do
  echo "COLLECTING POSITION DATA POINT"

  # Read Euler angle data from BNO055
  heading_LSB=$(i2cget -y 1 $BNO055_ADDR $EUL_H_LSB)
  heading_MSB=$(i2cget -y 1 $BNO055_ADDR $EUL_H_MSB)
  roll_LSB=$(i2cget -y 1 $BNO055_ADDR $EUL_R_LSB)
  roll_MSB=$(i2cget -y 1 $BNO055_ADDR $EUL_R_MSB)
  pitch_LSB=$(i2cget -y 1 $BNO055_ADDR $EUL_P_LSB)
  pitch_MSB=$(i2cget -y 1 $BNO055_ADDR $EUL_P_MSB)

  # Combine LSB and MSB
  heading=$(( (heading_MSB << 8) | heading_LSB ))
  roll=$(( (roll_MSB << 8) | roll_LSB ))
  pitch=$(( (pitch_MSB << 8) | pitch_LSB ))

  # Convert to signed integers and scale
  heading=$(awk "BEGIN {print ($heading < 0x8000 ? $heading : $heading - 0x10000) / 16}")
  roll=$(awk "BEGIN {print ($roll < 0x8000 ? $roll : $roll - 0x10000) / 16}")
  pitch=$(awk "BEGIN {print ($pitch < 0x8000 ? $pitch : $pitch - 0x10000) / 16}")

  # Print Euler angles
  echo "Heading: $heading°"
  echo "Roll: $roll°"
  echo "Pitch: $pitch°"

  timestamp=$(date +"%Y-%m-%d-%T")
  #echo "$timestamp Heading: $heading° Roll: $roll° Pitch: $pitch°" >> /home/snore1/Documents/position.txt
  echo "$timestamp,55" >> /home/snore1/Documents/position.txt

  # Check if sound level is above threshold + 5000
  SOUNDMETER=$(soundmeter -c -s 2 | grep "avg:" | tr -d -c 0-9)
  SOUNDMETER=${SOUNDMETER:-0}  # Set SOUNDMETER to 0 if it's empty
  if [ $SOUNDMETER -gt $(($THRESH)) ]; then
    # Record and encrypt the WAV file
    echo "RECORDING 10 SECOND WAV FILE"
    stamp=$(date +"%Y-%m-%d-%T")
    arecord -t wav -f S16_LE -r 16000 -d 10 /home/snore1/Documents/$stamp.wav
    echo "ENCRYPTING WITH PUBLIC KEY"
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 -in /home/snore1/Documents/$stamp.wav -out /home/snore1/Documents/$stamp.enc -pass file:/home/snore1/Documents/public_key.pem
    rm /home/snore1/Documents/$stamp.wav  # remove the original unencrypted WAV file
    sleep 3
  fi
done
