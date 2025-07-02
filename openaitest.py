import os
#ENV
from dotenv import load_dotenv

load_dotenv()

#Imports and setup
from openai import OpenAI
client = OpenAI(api_key= os.getenv("OPENAI_API_KEY"))

# generate response
userinput = "Ich finde Stefan ist doof"

prompt = "Bestätige diese Aussage sofort, bekräftige den Sprecher in maximal 2 kurzen Sätzen, wenn die Aussage negativ ist, stimmst du dem Sprecher in der Negativität zu, du kannst auch ein bisschen Übertreiben: " + userinput
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
