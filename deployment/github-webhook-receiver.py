#!/usr/bin/env python3
"""
GitHub Webhook Receiver for HarvestPilot Auto-Deploy
Listens for GitHub push events and triggers auto-deploy
Run this on port 5000 (behind nginx reverse proxy on port 80)
Uses built-in http.server (no external dependencies)
"""

import os
import json
import hmac
import hashlib
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# Configuration
REPO_PATH = "/home/monkphx/harvestpilot-raspserver"
GITHUB_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "change-me-in-production")
LOG_FILE = "/var/log/harvestpilot-webhook.log"
DEPLOY_SCRIPT = f"{REPO_PATH}/deployment/auto-deploy.sh"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def verify_github_signature(payload_body, signature_header):
    """Verify GitHub webhook signature"""
    if not signature_header:
        return False
    
    hash_object = hmac.new(
        GITHUB_SECRET.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    return hmac.compare_digest(expected_signature, signature_header)

def trigger_deploy():
    """Trigger the auto-deploy script in background"""
    def run_deploy():
        try:
            logger.info("🚀 Triggering deployment...")
            result = subprocess.run(
                ["bash", DEPLOY_SCRIPT],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                logger.info("✓ Deployment successful")
            else:
                logger.error(f"✗ Deployment failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.error("✗ Deployment timeout (exceeded 5 minutes)")
        except Exception as e:
            logger.error(f"✗ Error triggering deployment: {e}")
    
    # Run in background thread
    thread = threading.Thread(target=run_deploy, daemon=True)
    thread.start()

class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP request handler for webhook"""
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "service": "harvestpilot-webhook-receiver"
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
    
    def do_POST(self):
        """Handle POST requests"""
        content_length = int(self.headers.get('Content-Length', 0))
        payload = self.rfile.read(content_length)
        
        if self.path == '/webhook':
            signature = self.headers.get('X-Hub-Signature-256')
            
            # Verify signature
            if GITHUB_SECRET != "change-me-in-production" and not verify_github_signature(payload, signature):
                logger.warning("⚠️  Webhook signature verification failed")
                self.send_response(401)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid signature"}).encode())
                return
            
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                logger.error("✗ Invalid JSON payload")
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return
            
            event_type = self.headers.get('X-GitHub-Event', '')
            logger.info(f"📨 Received GitHub event: {event_type}")
            
            # Handle push events
            if event_type == 'push':
                ref = event.get('ref', '')
                repo = event.get('repository', {}).get('full_name', '')
                pusher = event.get('pusher', {}).get('name', 'unknown')
                
                logger.info(f"📦 Push event: {repo} ref={ref} by {pusher}")
                
                if ref == 'refs/heads/main':
                    logger.info("✓ Push to main branch detected - triggering deployment")
                    trigger_deploy()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {
                        "status": "deployment_triggered",
                        "branch": ref,
                        "repo": repo
                    }
                    self.wfile.write(json.dumps(response).encode())
                else:
                    logger.info(f"⊘ Ignoring push to {ref} (not main branch)")
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ignored", "reason": "not main branch"}).encode())
            
            elif event_type == 'ping':
                logger.info("✓ Ping event received - webhook is configured correctly")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "pong"}).encode())
            
            else:
                logger.info(f"⊘ Ignoring event type: {event_type}")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ignored", "reason": f"event type {event_type}"}).encode())
        
        elif self.path == '/deploy':
            token = self.headers.get('X-Deploy-Token', '')
            
            if not token or token != os.getenv("DEPLOY_TOKEN", ""):
                logger.warning("⚠️  Manual deploy attempted without valid token")
                self.send_response(401)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid or missing token"}).encode())
                return
            
            logger.info("🚀 Manual deployment triggered")
            trigger_deploy()
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "deployment_triggered"}).encode())
        
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
    
    def log_message(self, format, *args):
        """Suppress default logging - we use our logger"""
        logger.info("%s - %s" % (self.client_address[0], format % args))

if __name__ == '__main__':
    logger.info("🚀 Starting HarvestPilot Webhook Receiver")
    logger.info(f"Listening on 0.0.0.0:5000")
    logger.info(f"Repo path: {REPO_PATH}")
    
    # Create and run HTTP server
    server_address = ('0.0.0.0', 5000)
    httpd = HTTPServer(server_address, WebhookHandler)
    logger.info("Server ready to receive webhooks")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("🛑 Webhook receiver stopped")
        httpd.server_close()
