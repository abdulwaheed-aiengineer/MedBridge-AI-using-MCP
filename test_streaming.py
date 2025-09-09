#!/usr/bin/env python3
"""
Simple test script to verify streaming chat functionality
"""
import asyncio
import aiohttp
import json

async def test_streaming():
    async with aiohttp.ClientSession() as session:
        # Test the streaming endpoint
        async with session.post(
            'http://localhost:8000/chat/stream',
            json={
                'session_id': 'test-session',
                'user': 'I have a headache, can you help me find a doctor?',
                'language': 'en'
            }
        ) as response:
            print(f"Status: {response.status}")
            
            if response.status == 200:
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])
                            if 'content' in data:
                                print(f"Content: {data['content']}", end='', flush=True)
                            elif 'done' in data:
                                print("\n--- Stream completed ---")
                                break
                            elif 'error' in data:
                                print(f"\nError: {data['error']}")
                                break
                        except json.JSONDecodeError:
                            print(f"Failed to parse: {line}")
            else:
                text = await response.text()
                print(f"Error: {text}")

if __name__ == "__main__":
    print("Testing streaming chat functionality...")
    asyncio.run(test_streaming()) 