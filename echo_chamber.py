import os
import sys
import random
import time
import threading
import numpy as np
import wave
import pyaudio
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
import sounddevice as sd
from scipy.io.wavfile import write
import whisper
import pyttsx3
import shutil

# === CONFIGURATION ===
BACKGROUND_WAV = "sounds/Block_3_Sounds_mixdown.wav"
CLAP_WAV = "sounds/applaus.wav"
RECORD_SECONDS = 5
THRESHOLD = 0.0008  # Adjust for your mic/noise
USERSOUNDS_DIR = "usersounds"

# === BACKGROUND SOUND LOOP ===
class BackgroundPlayer(threading.Thread):
    def __init__(self, statement_files, clap_file):
        super().__init__()
        self.statement_files = statement_files
        self.clap_file = clap_file
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self.daemon = True

    def run(self):
        idx = 0
        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                time.sleep(0.1)
                continue
            # Play statement
            play_wav_file_blocking(self.statement_files[idx])
            if self._stop_event.is_set() or self._pause_event.is_set():
                continue
            # Play clap
            play_wav_file_blocking(self.clap_file)
            idx = (idx + 1) % len(self.statement_files)

    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    def stop(self):
        self._stop_event.set()

# === PLAY CLAP SOUND ===
def play_wav_file_blocking(filepath):
    if sys.platform.startswith("win"):
        import winsound
        winsound.PlaySound(filepath, winsound.SND_FILENAME)
    else:
        os.system(f"aplay {filepath}")

def play_wav_file_nonblocking(filepath):
    if sys.platform.startswith("win"):
        import winsound
        threading.Thread(target=winsound.PlaySound, args=(filepath, winsound.SND_FILENAME)).start()
    else:
        os.system(f"aplay {filepath} &")  # Non-blocking on Linux

def play_clap():
    play_wav_file_nonblocking(CLAP_WAV)

def get_random_usersound():
    files = [os.path.join(USERSOUNDS_DIR, f) for f in os.listdir(USERSOUNDS_DIR) if f.endswith(".wav")]
    return random.choice(files) if files else None

def get_statement_files():
    return [f"sounds/{i}.wav" for i in range(1, 7) if os.path.exists(f"sounds/{i}.wav")]

# === VOICE ACTIVITY DETECTION ===
def wait_for_voice(bg_player, threshold=THRESHOLD, duration=0.5, fs=44100):
    print("⏳ Warte auf Spracheingabe...")
    while True:
        audio = sd.rec(int(duration * fs), samplerate=fs, channels=1)
        sd.wait()
        volume_norm = np.linalg.norm(audio) / len(audio)
        print(f"Detected volume: {volume_norm:.5f}")
        if volume_norm > threshold:
            print("🎤 Sprache erkannt!")
            bg_player.pause()
            return audio  # Return the buffer that triggered detection

def record_and_transcribe(duration=RECORD_SECONDS, filename="input.wav", initial_audio=None):
    fs = 44100
    if initial_audio is not None:
        print("🎤 Aufnahme läuft (inkl. Start)...")
        remaining_duration = duration - (len(initial_audio) / fs)
        if remaining_duration > 0:
            audio_rest = sd.rec(int(remaining_duration * fs), samplerate=fs, channels=1)
            sd.wait()
            audio = np.concatenate((initial_audio, audio_rest), axis=0)
        else:
            audio = initial_audio
    else:
        print("🎤 Sprich jetzt...")
        audio = sd.rec(int(duration * fs), samplerate=fs, channels=1)
        sd.wait()
    write(filename, fs, audio)
    print("🎧 Aufnahme beendet. Transkribiere...")
    play_clap()
    model = whisper.load_model("base")
    result = model.transcribe(filename)
    print(f"🗣 Erkannt: {result['text']}")
    return result['text']

def build_prompt_and_generate(userinput):
    prompt = "Benutze diesen Userinput, um eine bestätigende, aufbauende Antwort zu schreiben, welche maximal einen satz lang ist: " + userinput
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Du bist ein bestätigender, aufbauender Gesprächspartner, der den User als Gottheit oder religiösen Führer ansieht."},
            {"role": "user", "content": prompt}
        ]
    )
    print(response.choices[0].message.content)
    return response.choices[0].message.content

def speak(text):
    print(f"📢 Echo: {text}")
    engine = pyttsx3.init()
    for voice in engine.getProperty('voices'):
        if "de" in voice.languages or "german" in voice.name.lower():
            engine.setProperty('voice', voice.id)
            break
    engine.say(text)
    engine.runAndWait()

# === MAIN LOOP ===
if __name__ == "__main__":
    os.makedirs(USERSOUNDS_DIR, exist_ok=True)
    statement_files = get_statement_files()
    if not statement_files:
        print("Fehler: Keine Statement-Sounds in 'sounds/1.wav' bis 'sounds/6.wav' gefunden!")
        sys.exit(1)
    bg_player = BackgroundPlayer(statement_files, CLAP_WAV)
    bg_player.start()
    try:
        while True:
            bg_player.resume()
            initial_audio = wait_for_voice(bg_player)
            bg_player.pause()
            userinput = record_and_transcribe(initial_audio=initial_audio)
            timestamp = int(time.time())
            usersound_path = os.path.join(USERSOUNDS_DIR, f"userinput_{timestamp}.wav")
            shutil.copy("input.wav", usersound_path)

            response_text = build_prompt_and_generate(userinput)
            speak(response_text)
            play_wav_file_blocking(CLAP_WAV)
            # After handling, background resumes automatically at top of loop
    except KeyboardInterrupt:
        print("Beende Programm...")
        bg_player.stop()