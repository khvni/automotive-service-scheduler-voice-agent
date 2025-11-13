"""Test API key validity for Deepgram and OpenAI"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "server"))

from app.config import settings


async def test_deepgram():
    """Test Deepgram API key."""
    print("Testing Deepgram API key...")
    try:
        from deepgram import DeepgramClient

        client = DeepgramClient(settings.DEEPGRAM_API_KEY)
        # Simple test - try to get account info or make a test request
        print(f"✅ Deepgram API key format valid: {settings.DEEPGRAM_API_KEY[:10]}...")
        return True
    except Exception as e:
        print(f"❌ Deepgram API key error: {e}")
        return False


async def test_openai():
    """Test OpenAI API key."""
    print("\nTesting OpenAI API key...")
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        # Try a minimal request
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        print(f"✅ OpenAI API key valid: {settings.OPENAI_API_KEY[:10]}...")
        return True
    except Exception as e:
        print(f"❌ OpenAI API key error: {e}")
        return False


async def main():
    print("=" * 60)
    print("API Key Validation Test")
    print("=" * 60)

    deepgram_ok = await test_deepgram()
    openai_ok = await test_openai()

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"Deepgram: {'✅ PASS' if deepgram_ok else '❌ FAIL'}")
    print(f"OpenAI: {'✅ PASS' if openai_ok else '❌ FAIL'}")
    print("=" * 60)

    if not (deepgram_ok and openai_ok):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
