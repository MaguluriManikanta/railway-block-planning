import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("ERROR: GROQ_API_KEY was not found.")
else:
    print("API key found!")

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "user",
                "content": "Say hello. Tell me that the Groq API is working."
            }
        ]
    )

    print("\nGroq response:")
    print(response.choices[0].message.content)