#   _____                        _
#  / ____|                      | |
# | (___  _ __   ___  _ __ _ __ | |__   ___ _   _ ___
#  \___ \| '_ \ / _ \| '__| '_ \| '_ \ / _ \ | | / __|
#  ____) | | | | (_) | |  | |_) | | | |  __/ |_| \__ \
# |_____/|_| |_|\___/|_|  | .__/|_| |_|\___|\__,_|___/ HUB SCRIPT
#                         | |
#                         |_|

import os
import subprocess
import paramiko
import hashlib
import tensorflow as tf
import tensorflow_hub as hub
import numpy as np
import csv
from datetime import datetime
import matplotlib.pyplot as plt
from IPython.display import Audio
from scipy.io import wavfile
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
import argparse

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Parse arguments
parser = argparse.ArgumentParser(description="Process Raspberry Pi audio data")
parser.add_argument("pi_id", type=int, help="ID number of the Raspberry Pi (1-15)")
parser.add_argument("first_name", help="First name of the patient")
parser.add_argument("last_name", help="Last name of the patient")
parser.add_argument("sex", help="Sex of the patient")
parser.add_argument("weight", help="Weight of the patient")
args = parser.parse_args()

pi_ips = ["192.168.0.227", "192.168.1.202", "192.168.1.203", "192.168.1.204",
          "192.168.1.205", "192.168.1.206", "192.168.1.207", "192.168.1.208",
          "192.168.1.209", "192.168.1.210", "192.168.1.211", "192.168.1.212",
          "192.168.1.213", "192.168.1.214", "192.168.1.215"]

# Mapping IDs to Raspberry Pi IP addresses
pi_id_ip_map = {i+1: pi_ips[i] for i in range(len(pi_ips))}

# Load path to private key
PRIVATE_KEY = "./private_key.pem"

# Choose classes of interest
SPEECH_CLASSES = ['Speech', 'Child speech, kid speaking', 'Conversation',
                  'Narration, monologue', 'Whispering', 'Chatter', 'Singing']
SNORE_CLASSES = ['Snoring', 'Breathing', 'Snort', 'Wheeze']

# Load the YAMnet model
model = hub.load('https://tfhub.dev/google/yamnet/1')

# Write patient info to a txt file
def write_patient_info(first_name, last_name, sex, weight, output_folder):
    file_name = os.path.join(output_folder, "patient_info.txt")
    with open(file_name, "w") as f:
        f.write(f"First Name: {first_name}\n")
        f.write(f"Last Name: {last_name}\n")
        f.write(f"Sex: {sex}\n")
        f.write(f"Weight: {weight}\n")

# Find the name of the class with the top score when mean-aggregated across frames.
def class_names_from_csv(class_map_csv_text):
  """Returns list of class names corresponding to score vector."""
  class_names = []
  with tf.io.gfile.GFile(class_map_csv_text) as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
      class_names.append(row['display_name'])

  return class_names

class_map_path = model.class_map_path().numpy()
class_names = class_names_from_csv(class_map_path)

def ensure_sample_rate(original_sample_rate, waveform,
                       desired_sample_rate=16000):
  """Resample waveform if required."""
  if original_sample_rate != desired_sample_rate:
    desired_length = int(round(float(len(waveform)) /
                               original_sample_rate * desired_sample_rate))
    waveform = scipy.signal.resample(waveform, desired_length)
  return desired_sample_rate, waveform

# Color ASCII art
print("\033[31m")  # Set color to red
print(r"""#   _____                        _
#  / ____|                      | |
# | (___  _ __   ___  _ __ _ __ | |__   ___ _   _ ___
#  \___ \| '_ \ / _ \| '__| '_ \| '_ \ / _ \ | | / __|
#  ____) | | | | (_) | |  | |_) | | | |  __/ |_| \__ \
# |_____/|_| |_|\___/|_|  | .__/|_| |_|\___|\__,_|___/
#                         | |
#                         |_|""")
print("\033[0m")  # Reset color
print("\033[33mHUB SCRIPT\n\n\033[0m", end='')


if args.pi_id not in pi_id_ip_map:
    print("Invalid ID number. Please try again.")
else:
    pi_id = args.pi_id
    pi_ip = pi_id_ip_map[pi_id]

    try:
        FIRST_NAME = args.first_name
        LAST_NAME = args.last_name
        PATIENT_SEX = args.sex
        PATIENT_WEIGHT = args.weight

        DATE = datetime.today().strftime('%Y-%m-%d')
        output_folder = f'./{LAST_NAME}-{DATE}/'
        os.makedirs(output_folder)

        write_patient_info(FIRST_NAME, LAST_NAME, PATIENT_SEX, PATIENT_WEIGHT, output_folder)

        # Connect to the Raspberry Pi using SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(pi_ip, username="evan", password="asdf")

        # Transfer the position.txt file
        sftp = ssh.open_sftp()
        sftp.get("/home/evan/Documents/position.txt", f"./{LAST_NAME}-{DATE}/position.txt")
        sftp.close()

        ssh.exec_command(f"rm /home/evan/Documents/position.txt")

        # Transfer all encrypted WAV files
        stdin, stdout, stderr = ssh.exec_command("find /home/evan/Documents -maxdepth 1 -name '*.enc'")  # CHANGED
        encrypted_wavs = stdout.read().decode().split()
        for encrypted_wav in encrypted_wavs:
            sftp = ssh.open_sftp()
            sftp.get(encrypted_wav, f"{encrypted_wav.split('/')[-1]}")
            sftp.close()

            # Delete the encrypted WAV file from the Raspberry Pi
            ssh.exec_command(f"rm {encrypted_wav}")  # CHANGED
            print("REMOVED WAV FILE FROM PI")

            encrypted_wav_name = f"{encrypted_wav.split('/')[-1]}"
            decrypted_wav = encrypted_wav_name.replace('.enc', '.wav')
            os.system(f"openssl enc -aes-256-cbc -d -salt -pbkdf2 -iter 100000 -in {encrypted_wav_name} -out ./{LAST_NAME}-{DATE}/{decrypted_wav} -pass file:{PRIVATE_KEY}")
            print("DECRYPTED WAV FILE")

            os.remove(f"{encrypted_wav_name}")
            print("REMOVED ENCRYPTED FILE LOCALLY")

        # Disconnect from the Raspberry Pi
        ssh.close()

        SNORE_COUNT = 0
        # Process all decrypted WAV files using the YAMNet algorithm
        for file in os.listdir(f"./{LAST_NAME}-{DATE}"):
            if file.endswith(".wav"):
                wav_file_name = f"./{LAST_NAME}-{DATE}/{file}"
                sample_rate, wav_data = wavfile.read(wav_file_name, 'rb')
                sample_rate, wav_data = ensure_sample_rate(sample_rate, wav_data)

                waveform = wav_data / tf.int16.max
                scores, embeddings, spectrogram = model(waveform)

                scores_np = scores.numpy()
                spectrogram_np = spectrogram.numpy()
                top_classes = np.argsort(scores_np.mean(axis=0))[-3:][::-1]
                top_class_names = [class_names[top_class] for top_class in top_classes]
                print(f'THE TOP THREE SOUNDS ARE: {top_class_names}')

                # Remove any fiels containing speech or not containing any snores
                if any(target_class in top_class_names for target_class in SPEECH_CLASSES) or (not any(target_class in top_class_names for target_class in SNORE_CLASSES)):
                  os.remove(wav_file_name)
                  print(f'DELETED: {wav_file_name} SPEECH OR IRRELEVANT AUDIO DETECTED')
                else:
                  SNORE_COUNT = SNORE_COUNT + 1;
                  print('SNORE EVENT DETECTED')

        print(f'\nPROCESSING COMPLETE FOR DEVICE #{pi_id}! {SNORE_COUNT} SNORE EVENTS DETECTED')

    # Catch any sort of execptions
    except Exception as e:
        print(f"Error processing Raspberry Pi {pi_ip}: {e}")
