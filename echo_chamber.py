# === Echo Chamber ===
# A simple Python script that listens for voice input, records it, and responds with enthusiastic agreement using OpenAI's GPT-3.5 Turbo model and Whisper for transcription.
import os
import sys
import random
import time
import threading
import numpy as np
import wave
import pyaudio
from dotenv import load_dotenv
import sounddevice as sd
from scipy.io.wavfile import write
import whisper
import pyttsx3
import shutil
import serial
import warnings
from vosk import Model, KaldiRecognizer
import json
from gtts import gTTS

warnings.filterwarnings("ignore", category=UserWarning)

# === SETUP ===
load_dotenv()
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# === CONFIGURATION ===
CLAP_WAV = "sounds/applaus.wav"
RECORD_SECONDS = 3
THRESHOLD = 0.0008  # Adjust for your mic/noise
USERSOUNDS_DIR = "usersounds"

# Adjust the port as needed (check with 'ls /dev/ttyACM*' or 'ls /dev/ttyUSB*' on Pi)
ARDUINO_PORT = '/dev/ttyACM0'
ARDUINO_BAUD = 9600

try:
    arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
    time.sleep(2)  # Wait for Arduino to reset
except Exception as e:
    print(f"Could not connect to Arduino: {e}")
    arduino = None

def set_arduino_state(state):
    if arduino:
        try:
            arduino.write(str(state).encode())
        except Exception as e:
            print(f"Serial write error: {e}")

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
        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                time.sleep(0.1)
                continue
            usersounds = [os.path.join(USERSOUNDS_DIR, f) for f in os.listdir(USERSOUNDS_DIR) if f.endswith(".wav")]
            all_files = self.statement_files + usersounds
            if not all_files:
                time.sleep(1)
                continue
            chosen_file = random.choice(all_files)
            play_wav_file_blocking(chosen_file, pause_event=self._pause_event, stop_event=self._stop_event)
            if self._stop_event.is_set() or self._pause_event.is_set():
                continue
            play_wav_file_blocking(self.clap_file, pause_event=self._pause_event, stop_event=self._stop_event)

    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    def stop(self):
        self._stop_event.set()

# === PLAY CLAP SOUND ===
def play_wav_file_blocking(filepath, pause_event=None, stop_event=None):
    print(f"Playing: {filepath}")  # Add this line for debugging
    wf = wave.open(filepath, 'rb')
    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True)
    chunk = 1024
    data = wf.readframes(chunk)
    while data:
        if stop_event and stop_event.is_set():
            break
        if pause_event and pause_event.is_set():
            break
        stream.write(data)
        data = wf.readframes(chunk)
    stream.stop_stream()
    stream.close()
    p.terminate()
    wf.close()

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
    bar_length = 40  # Length of the bar in characters
    while True:
        audio = sd.rec(int(duration * fs), samplerate=fs, channels=1)
        sd.wait()
        volume_norm = np.linalg.norm(audio) / len(audio)
        # Calculate bar fill
        fill = int(min(volume_norm / threshold, 1.0) * bar_length)
        bar = "[" + "#" * fill + "-" * (bar_length - fill) + "]"
        print(f"\rMic Level: {bar} {volume_norm:.5f} / {threshold:.5f}", end="", flush=True)
        if volume_norm > threshold:
            print("\n🎤 Sprache erkannt!")
            bg_player.pause()
            return audio  # Return the buffer that triggered detection

def record_and_transcribe(duration=RECORD_SECONDS, filename="input.wav", initial_audio=None):
    fs = 16000  # Vosk works best with 16kHz
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
    # Convert float32 audio to int16 PCM for Vosk
    audio_int16 = np.int16(audio * 32767)
    write(filename, fs, audio_int16)
    print("🎧 Aufnahme beendet. Transkribiere...")

    rec = KaldiRecognizer(vosk_model, fs)
    rec.AcceptWaveform(audio_int16.tobytes())
    result = rec.Result()
    text = json.loads(result).get("text", "")
    print(f"🗣 Erkannt: {text}")
    return text

def build_prompt_and_generate(userinput):
    prompt = "Bestätige diese Aussage sofort, bekräftige sie enthusiastisch oder lobend in maximal 2 kurzen Sätzen: " + userinput

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "Du bist ein sofort bestätigender, ehrfürchtiger Gesprächspartner. "
                    "Jede Aussage des Users ist für dich wahr, visionör und toll. "
                    "Du antwortest in maximal 2 Sätzen, ohne Fragen, nur Zustimmung, Lob oder Verstärkung. "
                    "Du behandelst den User wie eine vorbildsfigur oder einen guten Freund, welcher Unterstützung braucht oder eine absolute Wahrheit."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=80
    )

    print(response.choices[0].message.content)
    return response.choices[0].message.content

# #pyttsx3
# def speak(text):
#     print(f"📢 Echo: {text}")
#     engine = pyttsx3.init(driverName='espeak')
#     for voice in engine.getProperty('voices'):
#         if "de" in voice.languages or "german" in voice.name.lower():
#             engine.setProperty('voice', voice.id)
#             break
#     engine.say(text)
#     engine.runAndWait()

# #ngspeak native
# def speak(text):
#     print(f"📢 Echo: {text}")
#     os.system(f'espeak-ng -v de "{text}"')

#gTTS
def speak(text):
    print(f"📢 Echo: {text}")
    tts = gTTS(text, lang='de')
    tts.save("/tmp/tts.mp3")
    os.system('mpg123 /tmp/tts.mp3')

# === MAIN LOOP ===
if __name__ == "__main__":
    os.makedirs(USERSOUNDS_DIR, exist_ok=True)
    statement_files = get_statement_files()
    if not statement_files:
        print("Fehler: Keine Statement-Sounds in 'sounds/1.wav' bis 'sounds/6.wav' gefunden!")
        sys.exit(1)
    bg_player = BackgroundPlayer(statement_files, CLAP_WAV)
    bg_player.start()
    vosk_model = Model("vosk-model-small-de-0.15")  # adjust if needed
    try:
        while True:
            set_arduino_state(0)  # Background mode
            bg_player.resume()
            initial_audio = wait_for_voice(bg_player)
            bg_player.pause()
            set_arduino_state(1)  # User input mode
            userinput = record_and_transcribe(initial_audio=initial_audio)
            timestamp = int(time.time())
            usersound_path = os.path.join(USERSOUNDS_DIR, f"userinput_{timestamp}.wav")
            shutil.copy("input.wav", usersound_path)
            response_text = build_prompt_and_generate(userinput)
            bg_player.pause()  
            time.sleep(0.1)    
            speak(response_text)  
            time.sleep(0.1)    
            bg_player.resume() 

            play_wav_file_blocking(CLAP_WAV)
            # After handling, background resumes automatically at top of loop
    except KeyboardInterrupt:
        print("Beende Programm...")
        bg_player.stop()