import os
#ENV
from dotenv import load_dotenv

load_dotenv()

#Imports and setup
from openai import OpenAI
client = OpenAI(api_key= os.getenv("OPENAI_API_KEY"))

# generate response
response = client.responses.create(
    model="gpt-4.1",
    input="Write a one-sentence bedtime story about a unicorn."
)

print(response.output_text)
