#!/usr/bin/env python3
"""
Test script to verify Google API key works with basic APIs
"""
import os
import asyncio
import aiohttp

async def test_basic_google_api():
    """Test if the Google API key works with YouTube Data API (commonly enabled)"""
    
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("❌ No API key found. Please set GOOGLE_API_KEY environment variable.")
        return False
    
    print(f"🔑 Testing API key: {api_key[:10]}...{api_key[-4:]}")
    
    # Test with YouTube Data API (commonly available)
    url = "https://www.googleapis.com/youtube/v3/search"
    
    params = {
        'key': api_key,
        'q': 'test',
        'part': 'snippet',
        'maxResults': 1,
        'type': 'video'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print("🌐 Making test request to YouTube Data API...")
            
            async with session.get(url, params=params, timeout=10) as response:
                print(f"📡 Response status: {response.status}")
                
                if response.status == 200:
                    print("✅ API key is valid and working with YouTube Data API!")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Error: {error_text}")
                    return False
    
    except Exception as e:
        print(f"❌ Error testing API key: {e}")
        return False

async def main():
    print("🧪 Basic Google API Key Tester")
    print("=" * 40)
    
    success = await test_basic_google_api()
    
    if success:
        print("\n✅ Your Google API key is working!")
        print("Now you need to enable the Fact Check Tools API:")
        print("1. Go to: https://console.cloud.google.com/apis/library")
        print("2. Search for: 'Fact Check Tools API'")
        print("3. Click Enable")
        print("4. Then rerun: python test_google_api_key.py")

if __name__ == "__main__":
    asyncio.run(main())
