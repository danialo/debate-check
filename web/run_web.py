#!/usr/bin/env python3
"""
Simple direct startup for the web interface
"""

import sys
import os
from pathlib import Path

# Set up paths
project_root = Path(__file__).parent
web_dir = project_root / 'web'
sys.path.insert(0, str(project_root))

# Change to web directory
os.chdir(web_dir)

# Set Flask environment variables
os.environ['FLASK_APP'] = 'app.py'
os.environ['FLASK_ENV'] = 'development'

print("🎯 Starting Debate Analysis Web Interface...")
print(f"📁 Working directory: {web_dir}")

# Import Flask app
from app import app

if __name__ == '__main__':
    print("🌐 Server starting on http://127.0.0.1:8080")
    print("Press Ctrl+C to stop")
    print()
    
    try:
        app.run(host='127.0.0.1', port=8080, debug=True)
    except OSError as e:
        if "Address already in use" in str(e):
            print("❌ Port 8080 is already in use!")
            print("💡 Try a different port:")
            print("   python run_web.py")
            # Try port 8081
            try:
                print("🔄 Trying port 8081...")
                app.run(host='127.0.0.1', port=8081, debug=True)
            except OSError:
                print("❌ Port 8081 also in use. Please manually kill Flask processes:")
                print("   pkill -f python")
        else:
            print(f"❌ Error: {e}")
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")
