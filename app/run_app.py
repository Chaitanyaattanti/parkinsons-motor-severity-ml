#!/usr/bin/env python3
"""
MDS-UPDRS Part III Motor Examination Scoring App Runner
Starts a lightweight local HTTP server and opens the app in your default web browser.
"""

import http.server
import socketserver
import webbrowser
import os
import sys

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

def main():
    os.chdir(DIRECTORY)
    # Allow port reuse
    socketserver.TCPServer.allow_reuse_address = True
    
    port = PORT
    server = None
    for p in range(PORT, PORT + 10):
        try:
            server = socketserver.TCPServer(("", p), Handler)
            port = p
            break
        except OSError:
            continue

    if not server:
        print(f"Could not bind to any port in range {PORT}-{PORT+9}.")
        sys.exit(1)

    url = f"http://localhost:{port}/index.html"
    print("=" * 60)
    print(f"  MDS-UPDRS Part III: Motor Function Scoring Application")
    print("=" * 60)
    print(f"  Serving at: {url}")
    print(f"  Press Ctrl+C to stop the server.")
    print("=" * 60)

    # Open in browser
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()

if __name__ == "__main__":
    main()
