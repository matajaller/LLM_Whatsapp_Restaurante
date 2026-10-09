import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from tools import TOOLS, TOOL_FUNCTIONS, SESSION_TOOLS, new_customer_turn

load_dotenv(override=True)
client = Anthropic()
MODEL = os.getenv("MODEL", "claude-haiku-5-5")

# Safety limit so a confused model can't loop through tools forever
MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = """You are the WhatsApp assistant for Taquería El Fogón, a taquería in Monterrey, Mexico.

Rules:
- Always reply in Spanish, in a friendly, brief WhatsApp style (a few short lines, no long lists unless asked).
- Every fact about the menu, prices, availability, hours, address, payment or delivery must come from a tool call
  in this conversation. Never guess or invent a price, dish or schedule.
- Prices are in Mexican pesos (MXN).
- If a dish is marked unavailable, say it is not available today and suggest a similar available dish.
- If the customer asks about something unrelated to the restaurant, politely say you can only help with
  the taquería's menu, hours, location and orders.
- If you cannot answer from the tools (allergies, ingredients not listed, special requests, very large orders),
  say so honestly and never guess. Offer to pass the question to staff. If the customer accepts, ask for a phone
  number so staff can reply, call request_staff_handoff, and give them the ticket number.
  Never say you have passed something to staff unless request_staff_handoff succeeded.
- To take an order: ask for the customer's name if you don't have it, call quote_order, show the items and
  total, and ask them to confirm. Only call place_order after they clearly confirm in their next message.
  If they change anything, call quote_order again.
- After placing an order, give the customer their order number and total."""


def run_tool(name, tool_input, session_id):
    """Runs one tool requested by the model; errors go back to the model instead of crashing the chat."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"}), True
    try:
        # session_id is added here by the code, never chosen by the model
        if name in SESSION_TOOLS:
            result = func(**tool_input, session_id=session_id)
        else:
            result = func(**tool_input)
        return json.dumps(result, ensure_ascii=False), False
    except Exception as e:
        return json.dumps({"error": str(e)}), True


def chat_turn(messages, session_id="cli"):
    """Sends the conversation to the model, executes any tool calls, and returns the final reply text.
    `messages` is updated in place, so it keeps the full history for the next turn."""
    new_customer_turn(session_id)

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return "".join(block.text for block in response.content if block.type == "text")

        # The model asked for one or more tools: run each and send all results back together
        results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"   [tool] {block.name}({block.input})")
                output, is_error = run_tool(block.name, block.input, session_id)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                    "is_error": is_error,
                })
        messages.append({"role": "user", "content": results})

    return "Lo siento, tuve un problema procesando tu mensaje. ¿Puedes intentarlo de nuevo?"


if __name__ == "__main__":
    print(f"Taquería El Fogón - asistente ({MODEL}). Escribe 'salir' para terminar.\n")
    history = []
    while True:
        user_text = input("Tú: ").strip()
        if user_text.lower() in ("salir", "exit"):
            break
        if not user_text:
            continue
        history.append({"role": "user", "content": user_text})
        print(f"Asistente: {chat_turn(history)}\n")