import os
import sys
import time
import subprocess
from dotenv import load_dotenv
from gtts import gTTS

# Load environment variables and OpenAI client
load_dotenv()
from openai import OpenAI
oai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Prepare answers directory
ANSWERS_DIR = os.path.join(os.getcwd(), "answers")
os.makedirs(ANSWERS_DIR, exist_ok=True)

def build_prompt_and_generate(userinput):
    prompt = (
        "Bestätige diese Aussage sofort, bekräftige den Sprecher in maximal 2 kurzen Sätzen, "
        "wenn die Aussage negativ ist, stimmst du dem Sprecher in der Negativität zu, "
        "du kannst auch ein bisschen Übertreiben: " + userinput
    )
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
    return response.choices[0].message.content

def speak(text):
    print(f"📢 Echo: {text}")
    mp3_filename = f"tts_{int(time.time())}.mp3"
    mp3_path = os.path.join(ANSWERS_DIR, mp3_filename)
    tts = gTTS(text, lang='de', slow=False)
    tts.save(mp3_path)
    # Speed up the mp3 by 1.25x (change atempo as needed, e.g., 1.5 for 50% faster)
    fast_mp3_path = mp3_path.replace(".mp3", "_fast.mp3")
    subprocess.run([
        "ffmpeg", "-y", "-i", mp3_path, "-filter:a", "atempo=1.25", fast_mp3_path
    ], check=True)
    if sys.platform.startswith("win"):
        try:
            from playsound import playsound
            playsound(fast_mp3_path)
        except ImportError:
            print("playsound module not installed. Run 'pip install playsound'.")
    else:
        os.system(f'mpg123 "{fast_mp3_path}"')

if __name__ == "__main__":
    userinput = input("Geben Sie eine Aussage ein:\n")
    response_text = build_prompt_and_generate(userinput)
    speak(response_text)