"""HTTP Log Server — view Pi logs remotely from your browser.

Runs a lightweight HTTP server on the Pi that serves:
  GET /             → Live log viewer (auto-scrolling HTML page)
  GET /api/logs     → JSON: last N log lines (default 200)
  GET /api/logs/stream → SSE (Server-Sent Events): real-time log stream
  GET /api/health   → JSON: diagnostics + health summary
  GET /api/gpio     → JSON: current GPIO pin states
  POST /api/emergency-stop → Trigger emergency stop

Access from your browser: http://<pi-ip>:8880

The server reads from:
  1. In-memory ring buffer (captures all Python logging output)
  2. Log file on disk (logs/raspserver.log) for historical logs
"""

import logging
import threading
import json
import time
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from collections import deque
from datetime import datetime
from typing import Optional, Deque
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

# Default config
LOG_SERVER_PORT = int(os.getenv('LOG_SERVER_PORT', '8880'))
LOG_BUFFER_SIZE = 2000  # Keep last 2000 lines in memory
LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', 'logs/raspserver.log')


class LogBuffer(logging.Handler):
    """Logging handler that captures log records into a ring buffer.
    
    Attached to the root logger so ALL log output is captured.
    Thread-safe via deque's atomic append.
    """
    
    def __init__(self, max_lines: int = LOG_BUFFER_SIZE):
        super().__init__()
        self.buffer: Deque[dict] = deque(maxlen=max_lines)
        self._sse_clients: list = []  # SSE client queues
        self._lock = threading.Lock()
        
        # Format same as the main logger
        self.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
    
    def emit(self, record):
        try:
            entry = {
                'timestamp': self.format(record).split(' - ')[0],
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'formatted': self.format(record),
            }
            self.buffer.append(entry)
            
            # Push to SSE clients
            with self._lock:
                dead_clients = []
                for q in self._sse_clients:
                    try:
                        q.append(entry)
                    except Exception:
                        dead_clients.append(q)
                for q in dead_clients:
                    self._sse_clients.remove(q)
        except Exception:
            pass  # Never let logging handler crash the app
    
    def get_lines(self, count: int = 200, level: str = None) -> list:
        """Get last N log lines, optionally filtered by level."""
        lines = list(self.buffer)
        if level:
            level = level.upper()
            lines = [l for l in lines if l['level'] == level]
        return lines[-count:]
    
    def register_sse_client(self) -> deque:
        """Register a new SSE client and return its queue."""
        q = deque(maxlen=100)
        with self._lock:
            self._sse_clients.append(q)
        return q
    
    def unregister_sse_client(self, q: deque):
        """Remove an SSE client."""
        with self._lock:
            if q in self._sse_clients:
                self._sse_clients.remove(q)


# Global log buffer singleton
_log_buffer: Optional[LogBuffer] = None


def get_log_buffer() -> LogBuffer:
    """Get or create the global log buffer."""
    global _log_buffer
    if _log_buffer is None:
        _log_buffer = LogBuffer()
        # Attach to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(_log_buffer)
    return _log_buffer


class LogRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the log server."""
    
    # Suppress default access logging (we log it ourselves)
    def log_message(self, format, *args):
        pass
    
    def _send_json(self, data: dict, status: int = 200):
        """Send a JSON response."""
        body = json.dumps(data, indent=2, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def _send_html(self, html: str, status: int = 200):
        """Send an HTML response."""
        body = html.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        params = parse_qs(parsed.query)
        
        try:
            if path == '' or path == '/':
                self._handle_dashboard()
            elif path == '/api/logs':
                self._handle_logs(params)
            elif path == '/api/logs/stream':
                self._handle_sse_stream()
            elif path == '/api/health':
                self._handle_health()
            elif path == '/api/gpio':
                self._handle_gpio()
            else:
                self._send_json({'error': 'Not found'}, 404)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        
        try:
            if path == '/api/emergency-stop':
                self._handle_emergency_stop()
            else:
                self._send_json({'error': 'Not found'}, 404)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    # ── Handlers ──────────────────────────────────────────────────
    
    def _handle_logs(self, params):
        """GET /api/logs?count=200&level=ERROR"""
        buf = get_log_buffer()
        count = int(params.get('count', ['200'])[0])
        level = params.get('level', [None])[0]
        lines = buf.get_lines(count=count, level=level)
        self._send_json({
            'count': len(lines),
            'total_buffered': len(buf.buffer),
            'logs': lines,
        })
    
    def _handle_sse_stream(self):
        """GET /api/logs/stream — Server-Sent Events real-time log stream."""
        buf = get_log_buffer()
        q = buf.register_sse_client()
        
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            # Send last 50 lines as initial burst
            for entry in buf.get_lines(50):
                data = json.dumps(entry, default=str)
                self.wfile.write(f"data: {data}\n\n".encode('utf-8'))
            self.wfile.flush()
            
            # Stream new entries
            while True:
                if q:
                    entry = q.popleft()
                    data = json.dumps(entry, default=str)
                    self.wfile.write(f"data: {data}\n\n".encode('utf-8'))
                    self.wfile.flush()
                else:
                    # Send keepalive every 15s
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    time.sleep(0.5)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # Client disconnected
        finally:
            buf.unregister_sse_client(q)
    
    def _handle_health(self):
        """GET /api/health — health + diagnostics."""
        try:
            from ..services.diagnostics import DiagnosticsService
            # Try to get the running instance
            from ..core.server import RaspServer
            # Can't easily get singleton — return basic info
        except ImportError:
            pass
        
        import platform
        import socket
        
        health = {
            'status': 'online',
            'hostname': socket.gethostname(),
            'ip': _get_local_ip(),
            'platform': platform.platform(),
            'python': platform.python_version(),
            'timestamp': datetime.now().isoformat(),
            'log_server_port': LOG_SERVER_PORT,
            'log_buffer_size': len(get_log_buffer().buffer),
            'uptime_info': 'check /api/logs for operational data',
        }
        
        # Try to get GPIO controller state
        try:
            from ..services.gpio_actuator_controller import get_gpio_controller
            ctrl = get_gpio_controller()
            health['gpio_pins_initialized'] = len(ctrl._pins_initialized)
            health['hardware_serial'] = ctrl.hardware_serial
            health['device_id'] = ctrl.device_id
        except Exception:
            pass
        
        self._send_json(health)
    
    def _handle_gpio(self):
        """GET /api/gpio — current GPIO pin states."""
        try:
            from ..services.gpio_actuator_controller import get_gpio_controller
            ctrl = get_gpio_controller()
            states = ctrl.get_pin_states()
            # Convert int keys to strings for JSON
            self._send_json({
                'pins': {str(k): v for k, v in states.items()},
                'timestamp': datetime.now().isoformat(),
            })
        except Exception as e:
            self._send_json({'error': f'GPIO controller not available: {e}'}, 503)
    
    def _handle_emergency_stop(self):
        """POST /api/emergency-stop"""
        try:
            from ..services.gpio_actuator_controller import get_gpio_controller
            ctrl = get_gpio_controller()
            ctrl.emergency_stop()
            self._send_json({'status': 'emergency_stop_executed', 'timestamp': datetime.now().isoformat()})
        except Exception as e:
            self._send_json({'error': f'Emergency stop failed: {e}'}, 500)
    
    def _handle_dashboard(self):
        """GET / — live log viewer HTML page."""
        ip = _get_local_ip()
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HarvestPilot Pi Logs</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0d1117; color: #c9d1d9; font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace; font-size: 13px; }}
  .header {{ background: #161b22; padding: 12px 20px; border-bottom: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 10; }}
  .header h1 {{ font-size: 16px; color: #58a6ff; }}
  .header .status {{ display: flex; gap: 12px; align-items: center; }}
  .controls {{ background: #161b22; padding: 8px 20px; border-bottom: 1px solid #30363d; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
  .controls button {{ background: #21262d; color: #c9d1d9; border: 1px solid #30363d; padding: 4px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; }}
  .controls button:hover {{ background: #30363d; }}
  .controls button.danger {{ background: #da3633; color: white; border-color: #f85149; }}
  .controls button.danger:hover {{ background: #f85149; }}
  .controls select {{ background: #21262d; color: #c9d1d9; border: 1px solid #30363d; padding: 4px 8px; border-radius: 6px; font-size: 12px; }}
  .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
  .dot.green {{ background: #3fb950; }}
  .dot.red {{ background: #f85149; }}
  .dot.yellow {{ background: #d29922; }}
  #log-container {{ padding: 10px 20px; overflow-y: auto; height: calc(100vh - 100px); }}
  .log-line {{ padding: 2px 0; white-space: pre-wrap; word-break: break-all; line-height: 1.5; border-bottom: 1px solid #21262d; }}
  .log-line:hover {{ background: #161b22; }}
  .level-ERROR, .level-CRITICAL {{ color: #f85149; }}
  .level-WARNING {{ color: #d29922; }}
  .level-INFO {{ color: #c9d1d9; }}
  .level-DEBUG {{ color: #8b949e; }}
  .timestamp {{ color: #8b949e; }}
  .logger-name {{ color: #7ee787; }}
  .filter-active {{ background: #1f6feb !important; border-color: #58a6ff !important; }}
  #stats {{ font-size: 11px; color: #8b949e; }}
</style>
</head>
<body>
<div class="header">
  <h1>🌱 HarvestPilot Pi Logs</h1>
  <div class="status">
    <span id="stats">connecting...</span>
    <span class="dot" id="status-dot"></span>
  </div>
</div>
<div class="controls">
  <button onclick="clearLogs()">Clear</button>
  <button onclick="toggleAutoScroll()" id="btn-scroll">Auto-scroll: ON</button>
  <select id="level-filter" onchange="applyFilter()">
    <option value="">All Levels</option>
    <option value="CRITICAL">CRITICAL</option>
    <option value="ERROR">ERROR</option>
    <option value="WARNING">WARNING</option>
    <option value="INFO">INFO</option>
    <option value="DEBUG">DEBUG</option>
  </select>
  <button onclick="downloadLogs()">Download</button>
  <button class="danger" onclick="emergencyStop()">🚨 EMERGENCY STOP</button>
  <a href="/api/gpio" target="_blank" style="color:#58a6ff;text-decoration:none;font-size:12px;">GPIO State</a>
  <a href="/api/health" target="_blank" style="color:#58a6ff;text-decoration:none;font-size:12px;">Health</a>
</div>
<div id="log-container"></div>
<script>
const container = document.getElementById('log-container');
const statusDot = document.getElementById('status-dot');
const stats = document.getElementById('stats');
let autoScroll = true;
let lineCount = 0;
let levelFilter = '';

function addLogLine(entry) {{
  if (levelFilter && entry.level !== levelFilter) return;
  const div = document.createElement('div');
  div.className = 'log-line level-' + entry.level;
  div.innerHTML = '<span class="timestamp">' + escHtml(entry.timestamp) + '</span> - '
    + '<span class="logger-name">' + escHtml(entry.logger) + '</span> - '
    + '<b>' + entry.level + '</b> - '
    + escHtml(entry.message);
  container.appendChild(div);
  lineCount++;
  if (lineCount > 5000) {{ container.removeChild(container.firstChild); lineCount--; }}
  if (autoScroll) container.scrollTop = container.scrollHeight;
}}

function escHtml(s) {{ const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }}

function clearLogs() {{ container.innerHTML = ''; lineCount = 0; }}

function toggleAutoScroll() {{
  autoScroll = !autoScroll;
  document.getElementById('btn-scroll').textContent = 'Auto-scroll: ' + (autoScroll ? 'ON' : 'OFF');
  if (autoScroll) container.scrollTop = container.scrollHeight;
}}

function applyFilter() {{
  levelFilter = document.getElementById('level-filter').value;
  container.innerHTML = '';
  lineCount = 0;
  // Reload with filter
  fetch('/api/logs?count=500' + (levelFilter ? '&level=' + levelFilter : ''))
    .then(r => r.json())
    .then(data => data.logs.forEach(addLogLine));
}}

function downloadLogs() {{
  fetch('/api/logs?count=2000')
    .then(r => r.json())
    .then(data => {{
      const text = data.logs.map(l => l.formatted).join('\\n');
      const blob = new Blob([text], {{ type: 'text/plain' }});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'pi-logs-' + new Date().toISOString().slice(0,19).replace(/:/g,'-') + '.txt';
      a.click();
    }});
}}

function emergencyStop() {{
  if (confirm('🚨 EMERGENCY STOP — This will turn ALL pins OFF immediately. Continue?')) {{
    fetch('/api/emergency-stop', {{ method: 'POST' }})
      .then(r => r.json())
      .then(data => alert('Emergency stop executed: ' + JSON.stringify(data)))
      .catch(e => alert('Emergency stop failed: ' + e));
  }}
}}

// SSE connection
let evtSource;
function connectSSE() {{
  evtSource = new EventSource('/api/logs/stream');
  evtSource.onmessage = (e) => {{
    try {{
      const entry = JSON.parse(e.data);
      addLogLine(entry);
      stats.textContent = lineCount + ' lines | live';
      statusDot.className = 'dot green';
    }} catch(err) {{}}
  }};
  evtSource.onerror = () => {{
    statusDot.className = 'dot red';
    stats.textContent = 'disconnected — reconnecting...';
    evtSource.close();
    setTimeout(connectSSE, 3000);
  }};
  evtSource.onopen = () => {{
    statusDot.className = 'dot green';
    stats.textContent = 'connected';
  }};
}}
connectSSE();
</script>
</body>
</html>"""
        self._send_html(html)


def _get_local_ip() -> str:
    """Get the Pi's local IP address."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '0.0.0.0'


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTPServer that handles each request in a separate thread."""
    daemon_threads = True


class LogServer:
    """Manages the HTTP log server lifecycle."""
    
    def __init__(self, port: int = LOG_SERVER_PORT):
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the log server in a background thread."""
        # Ensure log buffer is capturing
        get_log_buffer()
        
        try:
            self._server = ThreadingHTTPServer(('0.0.0.0', self.port), LogRequestHandler)
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True,
                name='LogServer'
            )
            self._thread.start()
            
            ip = _get_local_ip()
            logger.info(f"📋 Log server started: http://{ip}:{self.port}")
            logger.info(f"   Dashboard:  http://{ip}:{self.port}/")
            logger.info(f"   Logs API:   http://{ip}:{self.port}/api/logs")
            logger.info(f"   Live stream: http://{ip}:{self.port}/api/logs/stream")
            logger.info(f"   GPIO state: http://{ip}:{self.port}/api/gpio")
            logger.info(f"   Health:     http://{ip}:{self.port}/api/health")
        except Exception as e:
            logger.error(f"Failed to start log server on port {self.port}: {e}")
    
    def stop(self):
        """Stop the log server."""
        if self._server:
            self._server.shutdown()
            logger.info("Log server stopped")


# Module-level convenience
_log_server: Optional[LogServer] = None


def start_log_server(port: int = LOG_SERVER_PORT) -> LogServer:
    """Start the global log server."""
    global _log_server
    if _log_server is None:
        _log_server = LogServer(port=port)
        _log_server.start()
    return _log_server


def stop_log_server():
    """Stop the global log server."""
    global _log_server
    if _log_server:
        _log_server.stop()
        _log_server = None
