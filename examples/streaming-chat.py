#!/usr/bin/env python3
"""
AI Lab Memory - Streaming Chat Example

This example demonstrates how to use streaming responses with AI Lab Memory.

Requirements:
    pip install openai

Usage:
    python streaming-chat.py "your query here"
"""

import sys
from openai import OpenAI


def main():
    # Configuration
    BASE_URL = "http://localhost:8083/v1"
    API_KEY = "sk-local"
    MODEL = "kimi-k2.5:cloud"

    # Get query from command line
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "Explain how hybrid search works in AI Lab Memory"

    print(f"🔍 Query: {query}")
    print("-" * 60)
    print()

    # Initialize client
    client = OpenAI(
        base_url=BASE_URL,
        api_key=API_KEY
    )

    try:
        # Create streaming request
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": query}],
            temperature=0.7,
            max_tokens=1000,
            stream=True
        )

        # Print streaming response
        print("🤖 Assistant: ", end="")

        full_response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                full_response += content

        print("\n")
        print("-" * 60)
        print(f"✅ Response complete ({len(full_response)} characters)")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure ai-mem is running:")
        print("  systemctl --user start ai-mem.service")
        sys.exit(1)


if __name__ == "__main__":
    main()
