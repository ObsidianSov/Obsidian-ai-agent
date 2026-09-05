import os
import requests

API_KEY = os.getenv("OPENROUTER_API_KEY")
URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL = "minimax/minimax-m2.7:free"

SYSTEM_PROMPT = """
You are Obsidian AI, a highly capable software engineering and problem-solving assistant.

Your primary mission is to help the user BUILD things.

You are exceptionally strong at:
- Python
- JavaScript and TypeScript
- HTML/CSS
- React
- Node.js
- APIs
- databases
- web applications
- mobile applications
- software architecture
- debugging
- automation
- UI/UX
- system design

When solving programming problems:
1. Understand the actual objective before writing code.
2. Prefer complete, working implementations over vague explanations.
3. Think carefully about architecture and edge cases.
4. Write clean, maintainable code.
5. Explain important decisions briefly.
6. When fixing code, identify the actual cause of the problem.
7. Never pretend code was tested if it wasn't.
8. If requirements are ambiguous, make a reasonable assumption and state it.

Your responses should be precise, technical and practical.
Do not use motivational filler.
"""

if not API_KEY:
    print("ERROR: OpenRouter API key not found.")
    print("Close and reopen Command Prompt, then try again.")
    exit()

print("=" * 60)
print("                 OBSIDIAN AI")
print("                 Minimax-m2.7")
print("=" * 60)
print("Software Engineering Mode")
print("Type 'exit' to quit.\n")

messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT
    }
]

while True:

    user_input = input("You: ")

    if user_input.lower() == "exit":
        print("\nObsidian AI shutting down.")
        break

    messages.append({
        "role": "user",
        "content": user_input
    })

    try:

        response = requests.post(
            URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": messages
            },
            timeout=120
        )

        data = response.json()

        if response.status_code != 200:
            print("\nERROR:")
            print(data)
            messages.pop()
            continue

        answer = data["choices"][0]["message"]["content"]

        messages.append({
            "role": "assistant",
            "content": answer
        })

        print("\nObsidian AI:")
        print(answer)
        print()

    except Exception as e:

        print("\nConnection error:")
        print(e)
        print()
