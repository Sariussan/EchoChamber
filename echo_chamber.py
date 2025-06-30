import os
from dotenv import load_dotenv

# speech to text to speech
import sounddevice as sd
from scipy.io.wavfile import write
import whisper
import pyttsx3

# setup
load_dotenv()

# chatgpt client
from openai import OpenAI
client = OpenAI(api_key= os.getenv("OPENAI_API_KEY"))


# Background loop - Inactive loop

# Passive loop

# Activate on input from arduino

# listen for voice & save what was said
def record_and_transcribe(duration=5, filename="input.wav"):
    fs = 44100
    print("🎤 Sprich jetzt...")
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    write(filename, fs, audio)
    print("🎧 Aufnahme beendet. Transkribiere...")
    model = whisper.load_model("base")
    result = model.transcribe(filename)
    print(f"🗣 Erkannt: {result['text']}")
    return result['text']

userinput = record_and_transcribe()
# build prompt
def build_prompt_and_generate(userinput):
    prompt = "Benutze diesen Userinput, um eine bestätigende, aufbauende Antwort zu schreiben, welche den User dazu ermutigt, weiter aussagen zu treffen: " + userinput

    # generate response
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # or another available model
        messages=[
            {"role": "system", "content": "Du bist ein bestätigender, aufbauender Gesprächspartner."},
            {"role": "user", "content": prompt}
        ]
    )
    print(response.choices[0].message.content)
    return response.choices[0].message.content

# play response
def speak(text):
    print(f"📢 Echo: {text}")
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

# After generating the response
response_text = build_prompt_and_generate(userinput)
speak(response_text)

# Reset to inactive state 