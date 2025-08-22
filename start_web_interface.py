#!/usr/bin/env python3
"""
Start the Debate Analysis Web Interface

This script starts the Flask web application for the debate analysis tool.
"""

import os
import sys
import socket
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Change to web directory
web_dir = project_root / 'web'
os.chdir(web_dir)

def find_available_port(start_port=8080, max_port=8100):
    """Find an available port starting from start_port"""
    for port in range(start_port, max_port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No available ports found between {start_port} and {max_port}")

# Import and run the Flask app
from web.app import app

if __name__ == '__main__':
    try:
        port = find_available_port()
        
        print("=" * 60)
        print("🎯 Debate Analysis Web Interface")
        print("=" * 60)
        print(f"📁 Project root: {project_root}")
        print(f"💾 Data storage: {web_dir / 'data'}")
        print(f"🌐 Starting web server on port {port}...")
        print(f"📝 Visit: http://localhost:{port}")
        print("=" * 60)
        print()
        
        app.run(debug=True, host='127.0.0.1', port=port)
        
    except KeyboardInterrupt:
        print("\n👋 Web interface stopped.")
    except Exception as e:
        print(f"\n❌ Error starting web interface: {e}")
        print("\n💡 Try killing any existing Flask processes:")
        print("   pkill -f 'python.*app.py'")
        sys.exit(1)
