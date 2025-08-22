#!/usr/bin/env python3
"""
Test script to verify Google Fact Check API key connectivity
"""
import os
import asyncio
import aiohttp
from typing import Optional

async def test_google_api_key(api_key: Optional[str] = None) -> bool:
    """Test if the Google Fact Check API key is valid and working"""
    
    if not api_key:
        api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("❌ No API key found. Please set GOOGLE_API_KEY environment variable.")
        return False
    
    print(f"🔑 Testing API key: {api_key[:10]}...{api_key[-4:]}")
    
    # Google Fact Check Tools API endpoint
    url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    
    params = {
        'key': api_key,
        'query': 'climate change',  # Simple test query
        'languageCode': 'en',
        'maxAgeDays': 365
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print("🌐 Making test request to Google Fact Check API...")
            
            async with session.get(url, params=params, timeout=10) as response:
                print(f"📡 Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    claims_count = len(data.get('claims', []))
                    print(f"✅ API key is valid! Found {claims_count} fact-check claims for test query.")
                    
                    # Show a sample claim if available
                    if claims_count > 0:
                        sample_claim = data['claims'][0]
                        claim_text = sample_claim.get('text', 'No text')
                        claimant = sample_claim.get('claimant', 'Unknown')
                        print(f"📋 Sample claim: \"{claim_text[:100]}...\" by {claimant}")
                    
                    return True
                
                elif response.status == 400:
                    error_text = await response.text()
                    print(f"❌ Bad request (400). Response: {error_text}")
                    if "API key not valid" in error_text:
                        print("💡 The API key appears to be invalid or not enabled for Fact Check API.")
                        print("🔧 Make sure you've enabled the 'Fact Check Tools API' in Google Cloud Console.")
                    return False
                
                elif response.status == 403:
                    error_text = await response.text()
                    print(f"❌ Forbidden (403). Response: {error_text}")
                    print("💡 The API key may not have permission for Fact Check Tools API.")
                    print("🔧 Check that the API is enabled and the key has proper permissions.")
                    return False
                
                else:
                    error_text = await response.text()
                    print(f"❌ Unexpected response ({response.status}): {error_text}")
                    return False
    
    except asyncio.TimeoutError:
        print("❌ Request timed out. Check your internet connection.")
        return False
    
    except Exception as e:
        print(f"❌ Error testing API key: {e}")
        return False

async def main():
    """Main function to test the API key"""
    print("🧪 Google Fact Check API Key Tester")
    print("=" * 40)
    
    success = await test_google_api_key()
    
    if success:
        print("\n🎉 Your API key is working! You can now use fact-checking with:")
        print("export GOOGLE_API_KEY='your_key_here'")
        print("python -m debate_claim_extractor --input your_file.txt --fact-check --verbose")
    else:
        print("\n🔧 API key test failed. Please check the suggestions above.")
        print("\n📋 Steps to fix:")
        print("1. Go to https://console.cloud.google.com/apis/library")
        print("2. Search for 'Fact Check Tools API' and enable it")
        print("3. Go to https://console.cloud.google.com/apis/credentials")
        print("4. Create/verify your API key has access to Fact Check Tools API")

if __name__ == "__main__":
    asyncio.run(main())
