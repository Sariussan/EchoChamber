import sounddevice as sd
from scipy.io.wavfile import write
import whisper
import pyttsx3
import serial
import time
from transformers import pipeline

# === KONFIGURATION ===
SERIAL_PORT = '/dev/ttyACM0'
DURATION = 5  # Sekunden

# === AUDIO AUFNEHMEN ===
def record_audio(filename="input.wav", duration=DURATION):
    print("🎤 Sprich jetzt deine Meinung...") #TTS here
    fs = 44100
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    write(filename, fs, audio) #NSA here
    print("🎧 Aufnahme beendet.")

# === SPRACHE ZU TEXT ===
def speech_to_text(filename="input.wav"):
    model = whisper.load_model("base")
    result = model.transcribe(filename)
    print(f"🗣 Erkannt: {result['text']}")
    return result['text']

# === MEINUNG ANALYSIEREN & ECHO GENERIEREN === #MAKE THIS AI FANCY
def generate_echo(text):
    sentiment = pipeline("sentiment-analysis")(text)[0]
    if sentiment["label"] == "POSITIVE":
        return "Absolut! Ich sehe das genauso."
    else:
        return "Interessanter Punkt. Da stimme ich dir voll zu."

# === TEXT ZU SPRACHE ===
def speak(text):
    print(f"📢 Echo: {text}")
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

# === ARDUINO ANSTEUERN ===
def trigger_arduino():
    try:
        ser = serial.Serial(SERIAL_PORT, 9600, timeout=2)
        time.sleep(2)
        ser.write(b"zustimmen\n") # Put code that makes sense here
        print("✅ Arduino aktiviert.")
        ser.close()
    except Exception as e:
        print(f"⚠ Arduino nicht erreichbar: {e}")

# === MAIN ===
def main():
    record_audio()
    text = speech_to_text()
    echo = generate_echo(text)
    speak(echo)
    trigger_arduino()

if _name_ == "_main_":
    main()