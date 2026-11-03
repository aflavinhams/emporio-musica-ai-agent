
from src.agent.agent import MusicStoreAgent
import re

def format_response(text: str) -> str:
    """Remove Markdown formatting unsupported by the terminal."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    return text

def main():
    print("=" * 55)
    print("EMPÓRIO DA MÚSICA — AI ASSISTANT")
    print("Sua música começa aqui!")
    print("Digite 'sair' para encerrar.")
    print("=" * 55)

    agent = MusicStoreAgent()

    while True:
        try:
            user_message = input("\nVocê: ").strip()

            if user_message.lower() in {
                "sair", "exit", "quit"
            }:
                print("\nAté logo! 🎵")
                break

            if not user_message:
                continue

            response = agent.chat(user_message)
            print(f"\nAssistente: {format_response(response)}")

        except (KeyboardInterrupt, EOFError):
            print("\nAtendimento encerrado.")
            break

        except Exception as error:
            print(
                f"\nErro durante o atendimento: "
                f"{type(error).__name__}: {error}"
            )


if __name__ == "__main__":
    main()
