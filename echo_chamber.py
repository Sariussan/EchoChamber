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

# === CONFIGURATION ===
BACKGROUND_WAV = "sounds/Block_3_Sounds_mixdown.wav"
CLAP_WAV = "sounds/klatschen.wav"
RECORD_SECONDS = 5
THRESHOLD = 0.0008  # Adjust for your mic/noise

# === BACKGROUND SOUND LOOP ===
class BackgroundPlayer(threading.Thread):
    def __init__(self, wav_path):
        super().__init__()
        self.wav_path = wav_path
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self.daemon = True

    def play_from_random(self):
        wf = wave.open(self.wav_path, 'rb')
        p = pyaudio.PyAudio()
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True)
        # Seek to random frame
        total_frames = wf.getnframes()
        random_frame = random.randint(0, total_frames - 1)
        wf.setpos(random_frame)
        chunk = 1024
        while not self._stop_event.is_set():
            # Check for pause before reading/writing
            if self._pause_event.is_set():
                time.sleep(0.1)
                continue
            data = wf.readframes(chunk)
            if not data:
                wf.rewind()
                random_frame = random.randint(0, total_frames - 1)
                wf.setpos(random_frame)
                continue
            stream.write(data)
        stream.stop_stream()
        stream.close()
        p.terminate()
        wf.close()

    def run(self):
        while not self._stop_event.is_set():
            self._pause_event.clear()
            self.play_from_random()

    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    def stop(self):
        self._stop_event.set()

# === PLAY CLAP SOUND ===
def play_clap():
    if sys.platform.startswith("win"):
        import winsound
        winsound.PlaySound(CLAP_WAV, winsound.SND_FILENAME)
    else:
        os.system(f"aplay {CLAP_WAV}")

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
    prompt = "Benutze diesen Userinput, um eine bestätigende, aufbauende Antwort zu schreiben, welche maximal 3 sätze lang ist: " + userinput
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Du bist ein bestätigender, aufbauender Gesprächspartner."},
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
    bg_player = BackgroundPlayer(BACKGROUND_WAV)
    bg_player.start()
    try:
        while True:
            initial_audio = wait_for_voice(bg_player)
            bg_player.pause()
            userinput = record_and_transcribe(initial_audio=initial_audio)
            response_text = build_prompt_and_generate(userinput)
            speak(response_text)
            time.sleep(1)
            bg_player.resume()
    except KeyboardInterrupt:
        print("Beende Programm...")
        bg_player.stop()