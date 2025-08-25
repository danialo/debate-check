#!/usr/bin/env python3
"""
Quick test for Google Fact Check API key.
"""

import os
import asyncio
import aiohttp
import sys

async def test_google_api_key():
    """Test if Google Fact Check API key works."""
    api_key = os.getenv('GOOGLE_FACT_CHECK_API_KEY')
    
    if not api_key:
        print("❌ No API key found!")
        print("💡 Set it with: export GOOGLE_FACT_CHECK_API_KEY='your-key-here'")
        return False
    
    print(f"🔑 Testing API key: {api_key[:10]}...{api_key[-4:]}")
    print("🔍 Testing with a simple claim...")
    
    # Test API endpoint
    url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    params = {
        'key': api_key,
        'query': 'climate change',
        'maxAgeDays': 365
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                print(f"📡 Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    claims = data.get('claims', [])
                    print(f"✅ API key works! Found {len(claims)} fact-checks")
                    
                    if claims:
                        print("📄 Sample results:")
                        for i, claim in enumerate(claims[:3]):
                            text = claim.get('text', 'No text')[:50]
                            reviews = claim.get('claimReview', [])
                            review_count = len(reviews)
                            print(f"   {i+1}. {text}... ({review_count} reviews)")
                    
                    return True
                    
                elif response.status == 400:
                    error_data = await response.json()
                    print(f"❌ Bad request: {error_data}")
                    return False
                    
                elif response.status == 403:
                    print("❌ Access forbidden! Check if:")
                    print("   • API key is correct")
                    print("   • Fact Check Tools API is enabled")
                    print("   • API key has proper restrictions")
                    return False
                    
                else:
                    print(f"❌ Unexpected status: {response.status}")
                    text = await response.text()
                    print(f"Response: {text[:200]}...")
                    return False
                    
    except Exception as e:
        print(f"❌ Error testing API: {e}")
        return False

async def main():
    """Main function."""
    print("🧪 Google Fact Check API Key Tester")
    print("=" * 40)
    
    success = await test_google_api_key()
    
    if success:
        print("\n🎉 SUCCESS! Your API key is working!")
        print("Now you can run:")
        print("  python realistic_fact_checker.py")
    else:
        print("\n💭 Troubleshooting:")
        print("1. Make sure you've enabled the Fact Check Tools API")
        print("2. Check that your API key is correct")
        print("3. Verify API key restrictions allow Fact Check Tools API")
        print("4. Try creating a new API key if issues persist")

if __name__ == "__main__":
    asyncio.run(main())
