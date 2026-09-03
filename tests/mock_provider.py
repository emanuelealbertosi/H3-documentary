"""Local test-only OpenAI-compatible endpoint. Never selected automatically by the app."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        if self.path!="/v1/models":self.send_error(404);return
        self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers()
        self.wfile.write(b'{"data":[{"id":"modello-di-prova"}]}')
    def do_POST(self):
        if self.path!="/v1/chat/completions":self.send_error(404);return
        self.rfile.read(int(self.headers.get("Content-Length",0)))
        self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers()
        self.wfile.write(json.dumps({"choices":[{"finish_reason":"stop","message":{"content":'{"ok":true,"lingua":"italiano"}'}}],"usage":{"prompt_tokens":20,"completion_tokens":10}}).encode())
if __name__=="__main__":
    print("Mock test-only provider on 127.0.0.1:18765",flush=True)
    ThreadingHTTPServer(("127.0.0.1",18765),Handler).serve_forever()
