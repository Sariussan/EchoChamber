import os
from dotenv import load_dotenv

import sounddevice as sd
from scipy.io.wavfile import write
import whisper
import pyttsx3
import sys

# Cross-platform sound playing
def play_clap():
    if sys.platform.startswith("win"):
        import winsound
        winsound.PlaySound("sounds/klatschen.wav", winsound.SND_FILENAME)
    else:
        try:
            import simpleaudio as sa
            wave_obj = sa.WaveObject.from_wave_file("sounds/klatschen.wav")
            play_obj = wave_obj.play()
        except ImportError:
            # Fallback to aplay if simpleaudio is not available
            os.system("aplay sounds/klatschen.wav")

# setup
load_dotenv()

# chatgpt client
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def record_and_transcribe(duration=5, filename="input.wav"):
    fs = 44100
    print("🎤 Sprich jetzt...")
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    write(filename, fs, audio)
    print("🎧 Aufnahme beendet. Transkribiere...")
    play_clap()  # Play sound during transcribing
    model = whisper.load_model("base")
    result = model.transcribe(filename)
    print(f"🗣 Erkannt: {result['text']}")
    return result['text']

userinput = record_and_transcribe()

def build_prompt_and_generate(userinput):
    prompt = "Benutze diesen Userinput, um eine bestätigende, aufbauende Antwort zu schreiben, welche den User dazu ermutigt, weiter aussagen zu treffen: " + userinput
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
    # Try to set German voice
    for voice in engine.getProperty('voices'):
        if "de" in voice.languages or "german" in voice.name.lower():
            engine.setProperty('voice', voice.id)
            break
    engine.say(text)
    engine.runAndWait()

response_text = build_prompt_and_generate(userinput)
speak(response_text)