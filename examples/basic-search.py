#!/usr/bin/env python3
"""
AI Lab Memory - Basic Search Example

This example demonstrates how to perform semantic search using the AI Lab Memory API.

Requirements:
    pip install openai

Usage:
    python basic-search.py "your query here"
"""

import sys
from openai import OpenAI


def main():
    # Configuration
    BASE_URL = "http://localhost:8083/v1"
    API_KEY = "sk-local"  # Change to your API key if configured differently
    MODEL = "kimi-k2.5:cloud"

    # Get query from command line or use default
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "What is RAG?"

    print(f"🔍 Query: {query}")
    print("-" * 50)

    # Initialize client
    client = OpenAI(
        base_url=BASE_URL,
        api_key=API_KEY
    )

    try:
        # Send chat request with memory retrieval
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": query}
            ],
            temperature=0.7,
            max_tokens=500
        )

        # Print response
        answer = response.choices[0].message.content
        print(f"\n📝 Answer:\n{answer}\n")

        # Print usage stats
        usage = response.usage
        print(f"📊 Tokens: {usage.prompt_tokens} (prompt) + {usage.completion_tokens} (completion) = {usage.total_tokens} total")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure ai-mem is running:")
        print("  systemctl --user start ai-mem.service")
        sys.exit(1)


if __name__ == "__main__":
    main()
