#!/usr/bin/env python3
"""
GitHub Webhook Receiver for HarvestPilot Auto-Deploy
Listens for GitHub push events and triggers auto-deploy
Run this on port 5000 (behind nginx reverse proxy on port 80)
"""

import os
import json
import hmac
import hashlib
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify

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

# Create Flask app
app = Flask(__name__)

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
    """Trigger the auto-deploy script"""
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
            return True
        else:
            logger.error(f"✗ Deployment failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("✗ Deployment timeout (exceeded 5 minutes)")
        return False
    except Exception as e:
        logger.error(f"✗ Error triggering deployment: {e}")
        return False

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "harvestpilot-webhook-receiver"
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """GitHub webhook receiver"""
    signature = request.headers.get('X-Hub-Signature-256')
    payload = request.get_data()
    
    # Verify signature
    if not verify_github_signature(payload, signature):
        logger.warning("⚠️  Webhook signature verification failed")
        return jsonify({"error": "Invalid signature"}), 401
    
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        logger.error("✗ Invalid JSON payload")
        return jsonify({"error": "Invalid JSON"}), 400
    
    event_type = request.headers.get('X-GitHub-Event')
    logger.info(f"📨 Received GitHub event: {event_type}")
    
    # Only process push events to main branch
    if event_type == 'push':
        ref = event.get('ref', '')
        repo = event.get('repository', {}).get('full_name', '')
        pusher = event.get('pusher', {}).get('name', 'unknown')
        
        logger.info(f"📦 Push event: {repo} ref={ref} by {pusher}")
        
        if ref == 'refs/heads/main':
            logger.info("✓ Push to main branch detected")
            success = trigger_deploy()
            
            if success:
                return jsonify({
                    "status": "deployment_triggered",
                    "branch": ref,
                    "repo": repo
                }), 200
            else:
                return jsonify({
                    "status": "deployment_failed",
                    "error": "See logs for details"
                }), 500
        else:
            logger.info(f"⊘ Ignoring push to {ref} (not main branch)")
            return jsonify({"status": "ignored", "reason": "not main branch"}), 200
    
    elif event_type == 'ping':
        logger.info("✓ Ping event received - webhook is configured correctly")
        return jsonify({"status": "pong"}), 200
    
    else:
        logger.info(f"⊘ Ignoring event type: {event_type}")
        return jsonify({"status": "ignored", "reason": f"event type {event_type}"}), 200

@app.route('/deploy', methods=['POST'])
def manual_deploy():
    """Manual deployment trigger (protected by secret token)"""
    token = request.headers.get('X-Deploy-Token')
    
    if not token or token != os.getenv("DEPLOY_TOKEN", ""):
        logger.warning("⚠️  Manual deploy attempted without valid token")
        return jsonify({"error": "Invalid or missing token"}), 401
    
    logger.info("🚀 Manual deployment triggered")
    success = trigger_deploy()
    
    if success:
        return jsonify({"status": "deployment_triggered"}), 200
    else:
        return jsonify({"status": "deployment_failed"}), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    logger.info("🚀 Starting HarvestPilot Webhook Receiver")
    logger.info(f"Listening on 0.0.0.0:5000")
    logger.info(f"Repo path: {REPO_PATH}")
    
    # Run on 0.0.0.0:5000 (behind reverse proxy)
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )
