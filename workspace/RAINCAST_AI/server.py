"""
Osogbo RainCast AI - Simple HTTP Server
Run this script to serve the RainCast AI dashboard
"""
import http.server
import socketserver
import webbrowser
from pathlib import Path

PORT = 8080
DIRECTORY = Path(__file__).parent

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)
    
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

def main():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"╔══════════════════════════════════════════════════════════╗")
        print(f"║           OSOGBO RAINCAST AI - SERVER STARTED             ║")
        print(f"╠══════════════════════════════════════════════════════════╣")
        print(f"║  🌧️  Dashboard: http://localhost:{PORT}                    ║")
        print(f"║  📍 Location:   Osogbo, Nigeria                           ║")
        print(f"║  🤖 AI Engine: Active                                     ║")
        print(f"╚══════════════════════════════════════════════════════════╝")
        print(f"\nServer running... Press Ctrl+C to stop\n")
        
        # Auto-open browser
        webbrowser.open(f'http://localhost:{PORT}')
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")

if __name__ == "__main__":
    main()
