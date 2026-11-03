
import re
from datetime import datetime
from pathlib import Path

from src.agent.agent import MusicStoreAgent


EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"

SCENARIOS = {
    "01_product_recommendation": (
        "Product Recommendation",
        "Product search with budget and availability constraints."
    ),
    "02_active_promotions": (
        "Active Promotions",
        "Promotion lookup and discount information."
    ),
    "03_return_policy": (
        "Return Policy",
        "Policy retrieval for online purchase returns."
    ),
    "04_order_tracking": (
        "Order Tracking",
        "Multi-turn order tracking with customer verification."
    ),
    "05_out_of_scope": (
        "Out of Scope",
        "Handling requests for products not sold by the store."
    ),
}


def format_response(text: str) -> str:
    """Remove Markdown formatting unsupported by the terminal."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(
        r"(?<!\*)\*([^*\n]+)\*(?!\*)",
        r"\1",
        text,
    )
    return text


def redact_personal_data(text: str) -> str:
    """Redact email addresses before saving conversations."""
    return re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[REDACTED_EMAIL]",
        text,
    )


def extract_tool_names(messages: list) -> list[str]:
    """Extract tool calls from the completed agent turn."""
    names = []

    for message in messages:
        if isinstance(message, dict):
            for call in message.get("tool_calls", []) or []:
                if isinstance(call, dict):
                    function = call.get("function", {})
                    name = function.get("name")
                    if name:
                        names.append(name)

    return names


def save_conversation(
    scenario_id: str,
    conversation: list[dict],
) -> Path:
    """Save an actual conversation as a Markdown example."""

    if scenario_id not in SCENARIOS:
        raise ValueError("Unknown scenario ID")

    if not conversation:
        raise ValueError("No conversation to save")

    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    title, description = SCENARIOS[scenario_id]
    file_path = EXAMPLES_DIR / f"{scenario_id}.md"

    # Never overwrite an existing example.
    if file_path.exists():
        suffix = 2
        while True:
            candidate = EXAMPLES_DIR / (
                f"{scenario_id}_{suffix}.md"
            )
            if not candidate.exists():
                file_path = candidate
                break
            suffix += 1

    lines = [
        f"# {title}",
        "",
        "## Scenario",
        description,
        "",
        "## Environment",
        "- Interface: Python CLI",
        "- LLM provider: Ollama (local)",
        "- Language: Brazilian Portuguese",
        "- Data source: provided CSV files and store policy PDF",
        "",
        "## Conversation",
        "",
    ]

    for turn in conversation:
        user_text = redact_personal_data(turn["user"])
        agent_text = redact_personal_data(turn["assistant"])
        tools = turn["tools"]

        lines.extend([
            "### Customer",
            user_text,
            "",
            "### Assistant",
            agent_text,
            "",
            "### Tools Executed",
        ])

        if tools:
            for tool in tools:
                lines.append(f"- `{tool}`")
        else:
            lines.append("- None")

        lines.append("")

    lines.extend([
        "## Notes",
        "- Transcript captured from an actual local execution.",
        "- Tool names were recorded from the agent conversation.",
        "- Email addresses were redacted for publication.",
        "- Tool arguments and raw results were not exported.",
        "- Accuracy should be reviewed before submission.",
        "",
    ])

    file_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return file_path


def main():
    print("=" * 55)
    print("EMPÓRIO DA MÚSICA — AI ASSISTANT")
    print("Sua música começa aqui!")
    print("Digite 'sair' para encerrar.")
    print("Digite '/save ID' para salvar uma conversa.")
    print("=" * 55)

    agent = MusicStoreAgent()
    conversation = []

    while True:
        try:
            user_message = input("\nVocê: ").strip()

            if user_message.lower() in {
                "sair", "exit", "quit"
            }:
                print("\nAtendimento encerrado.")
                break

            if not user_message:
                continue

            if user_message.startswith("/save"):
                parts = user_message.split(maxsplit=1)

                if len(parts) != 2:
                    print("\nInforme o ID do cenário:")
                    for scenario_id in SCENARIOS:
                        print(f"  {scenario_id}")
                    continue

                try:
                    path = save_conversation(
                        parts[1].strip(),
                        conversation,
                    )
                    print(f"\nConversa salva em: {path}")
                except ValueError as error:
                    print(f"\nErro: {error}")

                continue

            # Capture only new messages from this turn.
            previous_count = len(agent.messages)

            response = agent.chat(user_message)
            formatted = format_response(response)

            print(f"\nAssistente: {formatted}")

            new_messages = agent.messages[previous_count:]
            tool_names = extract_tool_names(new_messages)

            conversation.append({
                "user": user_message,
                "assistant": formatted,
                "tools": tool_names,
            })

        except (KeyboardInterrupt, EOFError):
            print("\nAtendimento encerrado.")
            break

        except Exception as error:
            print(
                "\nNão foi possível processar a mensagem: "
                f"{type(error).__name__}: {error}"
            )


if __name__ == "__main__":
    main()
