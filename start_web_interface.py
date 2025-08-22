#!/usr/bin/env python3
"""
Start the Debate Analysis Web Interface

This script starts the Flask web application for the debate analysis tool.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Change to web directory
web_dir = project_root / 'web'
os.chdir(web_dir)

# Import and run the Flask app
from web.app import app

if __name__ == '__main__':
    print("=" * 60)
    print("🎯 Debate Analysis Web Interface")
    print("=" * 60)
    print(f"📁 Project root: {project_root}")
    print(f"💾 Data storage: {web_dir / 'data'}")
    print("🌐 Starting web server...")
    print("📝 Visit: http://localhost:5000")
    print("=" * 60)
    print()
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 Web interface stopped.")
    except Exception as e:
        print(f"\n❌ Error starting web interface: {e}")
        sys.exit(1)
