#!/usr/bin/env python3
"""
Test alternative fact-checking APIs and approaches
"""
import os
import asyncio
import aiohttp
import json

async def test_custom_search_api():
    """Test Google Custom Search API for fact-checking"""
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("❌ No API key found")
        return False
    
    print("🔍 Testing Google Custom Search API (for fact-checking queries)...")
    
    # Custom Search API endpoint
    url = "https://www.googleapis.com/customsearch/v1"
    
    params = {
        'key': api_key,
        'cx': '017576662512468239146:omuauf_lfve',  # Google's fact-check search engine
        'q': 'climate change facts',
        'num': 3
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                print(f"📡 Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    items = data.get('items', [])
                    print(f"✅ Custom Search working! Found {len(items)} results")
                    
                    if items:
                        print(f"📋 Sample result: {items[0].get('title', 'No title')}")
                        print(f"🔗 Link: {items[0].get('link', 'No link')}")
                    
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Error: {error_text}")
                    return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def test_knowledge_graph_api():
    """Test Google Knowledge Graph API"""
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("❌ No API key found")
        return False
    
    print("🧠 Testing Google Knowledge Graph API...")
    
    url = "https://kgsearch.googleapis.com/v1/entities:search"
    
    params = {
        'query': 'climate change',
        'key': api_key,
        'limit': 3
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                print(f"📡 Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    items = data.get('itemListElement', [])
                    print(f"✅ Knowledge Graph working! Found {len(items)} entities")
                    
                    if items:
                        result = items[0].get('result', {})
                        print(f"📋 Sample entity: {result.get('name', 'No name')}")
                        print(f"📝 Description: {result.get('description', 'No description')[:100]}...")
                    
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Error: {error_text}")
                    return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def test_wikipedia_api():
    """Test Wikipedia API (free alternative)"""
    print("📚 Testing Wikipedia API (no auth required)...")
    
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/Climate_change"
    
    headers = {
        'User-Agent': 'DebateFactChecker/1.0 (https://github.com/user/debate-check)'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                print(f"📡 Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    title = data.get('title', 'No title')
                    extract = data.get('extract', 'No extract')
                    
                    print(f"✅ Wikipedia API working!")
                    print(f"📋 Title: {title}")
                    print(f"📝 Extract: {extract[:150]}...")
                    
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Error: {error_text}")
                    return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def main():
    print("🧪 Testing Alternative Fact-Checking APIs")
    print("=" * 50)
    
    # Test various APIs
    results = {}
    
    print("\n1️⃣ Testing Google Custom Search...")
    results['custom_search'] = await test_custom_search_api()
    
    print("\n2️⃣ Testing Google Knowledge Graph...")  
    results['knowledge_graph'] = await test_knowledge_graph_api()
    
    print("\n3️⃣ Testing Wikipedia API...")
    results['wikipedia'] = await test_wikipedia_api()
    
    print(f"\n📊 Results Summary:")
    for api, success in results.items():
        status = "✅ Working" if success else "❌ Failed"
        print(f"  {api}: {status}")
    
    working_apis = [api for api, success in results.items() if success]
    
    if working_apis:
        print(f"\n🎉 {len(working_apis)} API(s) are working!")
        print("💡 We can use these for fact-checking instead of the Google Fact Check Tools API")
    else:
        print(f"\n😔 No APIs are working with your current setup")
        print("💡 Consider using only the local database for now")

if __name__ == "__main__":
    asyncio.run(main())
