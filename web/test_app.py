#!/usr/bin/env python3
"""
Minimal Flask app to test if basic functionality works
"""

from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test App</title>
    </head>
    <body>
        <h1>Hello World!</h1>
        <p>This is a minimal Flask test app.</p>
        <p>If you can see this, Flask is working correctly.</p>
    </body>
    </html>
    ''')

@app.route('/test')
def api_status():
    return {'status': 'working', 'message': 'Flask API is functional'}

if __name__ == '__main__':
    print("Starting minimal Flask test app...")
    app.run(debug=True, host='127.0.0.1', port=8080)
