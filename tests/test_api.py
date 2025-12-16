#!/usr/bin/env python3
"""Quick test for OpenAI API connectivity"""

from openai import OpenAI

OPENAI_API_KEY = "sk-o92MoYgtEGcJrtvYEPS8t3BTWCwUfdg6o3HzdA67L3yWtddO"
OPENAI_BASE_URL = "https://api.gapgpt.app/v1"
MODEL_NAME = "gpt-4o-mini"

print(f"Testing API: {OPENAI_BASE_URL}")
print(f"Model: {MODEL_NAME}")
print("-" * 40)

try:
    client = OpenAI(
        api_key=OPENAI_API_KEY, 
        base_url=OPENAI_BASE_URL,
        timeout=60.0
    )
    
    print("Sending test request...")
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "user", "content": "سلام. فقط بگو: تست موفق"}
        ],
        temperature=0.3,
        timeout=60.0
    )
    
    print(f"Response: {response.choices[0].message.content}")
    print("✅ API is working!")
    
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
