import os
import sys
import time
from gtts import gTTS

ANSWERS_DIR = os.path.join(os.getcwd(), "answers")
os.makedirs(ANSWERS_DIR, exist_ok=True)

text = input("Geben Sie den Satz ein, der gesprochen werden soll:\n")

mp3_filename = f"tts_{int(time.time())}.mp3"
tts = gTTS(text, lang="de")
tts.save(os.path.join(ANSWERS_DIR, mp3_filename))

os.system(f"start {os.path.join(ANSWERS_DIR, mp3_filename)}")