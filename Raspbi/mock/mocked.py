import sounddevice as sd
import scipy.io.wavfile
import whisper
import pyttsx3
import transformers

# === KONFIGURATION ===
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

# === MOCK ARDUINO ANSTEUERUNG ===
def trigger_mock():
    print("✅ (Mock) Aktion ausgelöst.")

# === MAIN ===
def main():
    record_audio()
    text = speech_to_text()
    echo = generate_echo(text)
    speak(echo)
    trigger_mock()

if __name__ == "__main__":
    main()