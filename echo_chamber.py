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
import shutil
import serial
import warnings
from gtts import gTTS
from google.cloud import speech


warnings.filterwarnings("ignore", category=UserWarning)

# === SETUP ===
load_dotenv()
from openai import OpenAI
oai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
g_client = speech.SpeechClient()


# === CONFIGURATION ===
CLAP_WAV = "sounds/applaus.wav"
RECORD_SECONDS = 4
THRESHOLD = 0.00055  # Adjust for your mic/noise
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

def record_and_transcribe(filename="input.wav", initial_audio=None):
    fs = 16000
    if initial_audio is not None:
        print("🎤 Aufnahme läuft (inkl. Start)...")
        audio_rest = record_until_silence(threshold=THRESHOLD, fs=fs)
        audio = np.concatenate((initial_audio, audio_rest), axis=0)
    else:
        audio = record_until_silence(threshold=THRESHOLD, fs=fs)
    audio_int16 = np.int16(audio * 32767)
    write(filename, fs, audio_int16)
    print("🎧 Aufnahme beendet. Transkribiere...")

    # Use Google Speech-to-Text
    text = transcribe_file(filename)
    print(f"🗣 Erkannt: {text}")
    return text

def build_prompt_and_generate(userinput):
    prompt = "Bestätige diese Aussage sofort, bekräftige den Sprecher in maximal 2 kurzen Sätzen, wenn die Aussage negativ ist, stimmst du dem Sprecher in der Negativität zu, du kannst auch ein bisschen Übertreiben: " + userinput
    response = oai_client.chat.completions.create(
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
    tts = gTTS(text, lang='de', slow=False) 
    tts.save("/tmp/tts.mp3")
    os.system('mpg123 /tmp/tts.mp3')

def transcribe_file(speech_file):
    with open(speech_file, "rb") as audio_file:
        content = audio_file.read()
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="de-DE",
    )
    response = g_client.recognize(config=config, audio=audio)
    for result in response.results:
        print("Transcript: {}".format(result.alternatives[0].transcript))
    return response.results[0].alternatives[0].transcript if response.results else ""

def record_until_silence(threshold=THRESHOLD, silence_duration=1.2, max_record=10, fs=16000):
    print("🎤 Aufnahme läuft... (Sprich, Aufnahme stoppt nach Stille)")
    silence_chunks = int(silence_duration / 0.1)
    audio_buffer = []
    silent_chunks = 0
    max_chunks = int(max_record / 0.1)
    while True:
        chunk = sd.rec(int(0.1 * fs), samplerate=fs, channels=1)
        sd.wait()
        audio_buffer.append(chunk)
        volume_norm = np.linalg.norm(chunk) / len(chunk)
        if volume_norm < threshold:
            silent_chunks += 1
        else:
            silent_chunks = 0
        if silent_chunks >= silence_chunks or len(audio_buffer) >= max_chunks:
            break
    audio = np.concatenate(audio_buffer, axis=0)
    return audio

# === MAIN LOOP ===
if __name__ == "__main__":
    os.makedirs(USERSOUNDS_DIR, exist_ok=True)
    statement_files = get_statement_files()
    if not statement_files:
        print("Fehler: Keine Statement-Sounds in 'sounds/1.wav' bis 'sounds/6.wav' gefunden!")
        sys.exit(1)
    bg_player = BackgroundPlayer(statement_files, CLAP_WAV)
    bg_player.start()
    #vosk_model = Model("vosk-model-de-0.21")  # adjust if needed
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