#!/usr/bin/env python3
"""
AI Lab Memory - Hermes Agent Integration Example

This example demonstrates how to integrate Hermes Agent with AI Lab Memory.

Requirements:
    pip install openai

Usage:
    python hermes-integration.py
"""

from openai import OpenAI


def main():
    # Configuration
    BASE_URL = "http://localhost:8083/v1"
    API_KEY = "sk-local"
    MODEL = "kimi-k2.5:cloud"

    print("🤖 Hermes Agent + AI Lab Memory Integration")
    print("=" * 60)
    print()

    # Initialize client (same as Hermes uses)
    client = OpenAI(
        base_url=BASE_URL,
        api_key=API_KEY
    )

    # Conversation with memory context
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant with access to long-term memory. When answering, cite relevant memories when appropriate."
        },
        {
            "role": "user",
            "content": "What are the cmake flags to compile llama.cpp with CUDA support?"
        }
    ]

    print("💬 User: What are the cmake flags to compile llama.cpp with CUDA support?")
    print()

    try:
        # Send request
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=500,
            stream=False
        )

        # Print response
        answer = response.choices[0].message.content
        print(f"🤖 Assistant:\n{answer}\n")

        # Print memory info (if available in response)
        if hasattr(response, 'system_fingerprint'):
            print(f"🧠 System fingerprint: {response.system_fingerprint}")

        # Print usage
        usage = response.usage
        print(f"📊 Tokens: {usage.prompt_tokens} + {usage.completion_tokens} = {usage.total_tokens}")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure ai-mem is running: systemctl --user start ai-mem.service")
        print("  2. Check health: curl http://localhost:8083/health")
        print("  3. Verify Qdrant: curl http://localhost:6333/collections")
        return 1

    # Follow-up question (tests conversation memory)
    print("\n" + "=" * 60)
    print("💬 Follow-up: What about FP16 optimization?")
    print()

    messages.append({
        "role": "assistant",
        "content": answer
    })
    messages.append({
        "role": "user",
        "content": "What about FP16 optimization?"
    })

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )

        answer = response.choices[0].message.content
        print(f"🤖 Assistant:\n{answer}\n")

        usage = response.usage
        print(f"📊 Tokens: {usage.prompt_tokens} + {usage.completion_tokens} = {usage.total_tokens}")

    except Exception as e:
        print(f"❌ Error on follow-up: {e}")
        return 1

    print("\n✅ Integration test complete!")
    return 0


if __name__ == "__main__":
    exit(main())
