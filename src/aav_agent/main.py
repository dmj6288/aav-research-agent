import os
from dotenv import load_dotenv
from openai import OpenAI

def main() -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    print("Environment is configured correctly.")

if __name__ == "__main__":
    main()