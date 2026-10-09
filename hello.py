import os
from anthropic import Anthropic
from dotenv import load_dotenv

# Reads ANTHROPIC_API_KEY (and MODEL, once set) from the .env file
# override=True makes the .env value win over anything already set in Windows
load_dotenv(override=True)
client = Anthropic()

# Lists the models this key can use, newest first
models = [m.id for m in client.models.list(limit=10).data]
print("Available models:")
for m in models:
    print("  ", m)

# Uses MODEL from .env if set, otherwise the newest model on the list
model = os.getenv("MODEL") or models[0]
reply = client.messages.create(
    model=model,
    max_tokens=100,
    messages=[{"role": "user", "content": "Saluda en una frase como asistente de una taquería."}],
)
print(f"\nModel used: {model}")
print(reply.content[0].text)