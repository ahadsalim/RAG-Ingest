#!/usr/bin/env python3
"""
Legal Document Image Processor
================================
Processes images of legal documents (رای وحدت رویه) using AI vision,
extracts structured information, and provides a web interface for review.

Usage:
1. Set your OpenAI API key and base URL below
2. Place JPG images in the same directory as this script
3. Run: python legal_image_processor.py
4. Open http://localhost:5001 in your browser
"""

VERSION = "1.0.0"

# ============================================
# CONFIGURATION - SET THESE VALUES
# ============================================
OPENAI_API_KEY = "sk-o92MoYgtEGcJrtvYEPS8t3BTWCwUfdg6o3HzdA67L3yWtddO"
OPENAI_BASE_URL = "https://api.gapgpt.app/v1"

# Database connection
DB_CONFIG = {
    "host": "45.92.219.229",
    "port": 15432,
    "database": "ingest",
    "user": "ingest",
    "password": "rQXRweJEjVSD7tMKX4TrV3LQHDNhklt2"
}

# Model settings
MODEL_NAME = "gpt-4o"  # Vision model
BATCH_SIZE = 5  # Process 5 images at a time

# ============================================
# DO NOT MODIFY BELOW THIS LINE
# ============================================

import os
import json
import uuid
import base64
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI

app = Flask(__name__)

# Global state
state = {
    "status": "idle",  # idle, processing, waiting_approval
    "current_batch": 0,
    "total_images": 0,
    "processed_images": 0,
    "logs": [],
    "current_results": None,  # Current batch results waiting for approval
    "current_images": None,  # Current batch image filenames
    "script_dir": os.path.dirname(os.path.abspath(__file__)),
    "jpg_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "jpg")
}

def get_db_connection():
    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        cursor_factory=RealDictCursor
    )

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{ts}] {msg}"
    state["logs"].append(log_msg)
    print(log_msg)
    
    log_file = os.path.join(state["script_dir"], "ai_image.log")
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_msg + "\n")
    except Exception as e:
        print(f"Failed to write to log file: {e}")

def get_jpg_images():
    """Get all JPG images in the jpg subdirectory."""
    jpg_files = []
    jpg_dir = state["jpg_dir"]
    
    # Create jpg directory if it doesn't exist
    if not os.path.exists(jpg_dir):
        os.makedirs(jpg_dir)
        log(f"Created jpg directory: {jpg_dir}")
        return []
    
    for file in os.listdir(jpg_dir):
        if file.lower().endswith(('.jpg', '.jpeg')):
            jpg_files.append(file)
    return sorted(jpg_files)

def encode_image(image_path):
    """Encode image to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def build_vision_prompt():
    """Build prompt for GPT Vision."""
    system = """تو یک Legal Document Extractor هستی. تصاویر رای‌های وحدت رویه هیأت عمومی دیوان عالی کشور را تحلیل می‌کنی.

## ساختار تصاویر:
- رای شماره: [شماره] - [تاریخ شمسی]
- بسمه تعالی یا باسمه تعالی
- متن رای
- هیات عمومی دیوان عالی کشور (امضا - نباید در محتوا باشد)

## خروجی JSON (بدون هیچ متن اضافه):
{
  "results": [
    {
      "image_file": "filename.jpg",
      "title": "رأی وحدت رویه هیأت عمومی دیوان عالی کشور - [تاریخ شمسی]",
      "text_type": "رای",
      "content": "[تمام محتوای صفحه از شماره رای تا انتها بدون امضا]",
      "effective_date": "[تاریخ شمسی در فرمت YYYY/MM/DD]",
      "confidence": "[high/medium/low]"
    }
  ]
}

## نکات مهم:
1. تاریخ شمسی است (مثل 1346/4/22)
2. محتوا باید شامل شماره رای باشد
3. امضای "هیات عمومی دیوان عالی کشور" در محتوا نباشد
4. اگر تصویر واضح نیست، confidence را low بگذار"""

    user = """لطفاً تمام تصاویر زیر را تحلیل کن و برای هر کدام اطلاعات را استخراج کن."""
    
    return system, user

def call_gpt_vision(image_files):
    """Call GPT Vision API with multiple images."""
    log(f"Calling GPT Vision API ({MODEL_NAME}) for {len(image_files)} images...")
    
    try:
        client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=180.0
        )
        
        system, user = build_vision_prompt()
        
        # Build messages with images
        messages = [
            {"role": "system", "content": system}
        ]
        
        # Add user message with all images
        content = [{"type": "text", "text": user}]
        
        for img_file in image_files:
            img_path = os.path.join(state["jpg_dir"], img_file)
            base64_image = encode_image(img_path)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })
            log(f"Added image: {img_file}")
        
        messages.append({"role": "user", "content": content})
        
        log("Sending request to API...")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.1,
            max_tokens=4096
        )
        
        result = response.choices[0].message.content
        log(f"Got response: {len(result)} chars")
        
        # Extract JSON from response
        if result.strip().startswith('{'):
            return result
        
        import re
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            return json_match.group()
        
        log(f"Warning: No JSON found in response")
        return '{"results": []}'
        
    except Exception as e:
        log(f"API Error: {type(e).__name__}: {e}")
        raise

def process_next_batch():
    """Process next batch of images."""
    state["status"] = "processing"
    state["current_batch"] += 1
    
    # Get unprocessed images
    all_images = get_jpg_images()
    start_idx = (state["current_batch"] - 1) * BATCH_SIZE
    batch_images = all_images[start_idx:start_idx + BATCH_SIZE]
    
    if not batch_images:
        log("No more images to process!")
        state["status"] = "idle"
        return False
    
    state["current_images"] = batch_images
    log(f"Batch {state['current_batch']}: Processing {len(batch_images)} images...")
    
    try:
        response = call_gpt_vision(batch_images)
        
        # Save response to file for debugging
        response_file = os.path.join(state["script_dir"], f"batch{state['current_batch']}_response.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            f.write(response)
        log(f"Response saved to {response_file}")
        
        result = json.loads(response)
        results = result.get("results", [])
        
        log(f"Got {len(results)} results")
        
        # Build display data
        display_data = []
        for i, img_file in enumerate(batch_images):
            # Find matching result
            img_result = next((r for r in results if r.get('image_file') == img_file), None)
            
            if not img_result:
                # Create default result
                img_result = {
                    "image_file": img_file,
                    "title": f"رأی وحدت رویه هیأت عمومی دیوان عالی کشور - [تاریخ]",
                    "text_type": "رای",
                    "content": "",
                    "effective_date": "",
                    "confidence": "low"
                }
            
            # Read image for preview
            img_path = os.path.join(state["jpg_dir"], img_file)
            with open(img_path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode('utf-8')
            
            display_data.append({
                "image_file": img_file,
                "image_base64": img_base64,
                "title": img_result.get("title", ""),
                "text_type": img_result.get("text_type", "رای"),
                "content": img_result.get("content", ""),
                "effective_date": img_result.get("effective_date", ""),
                "confidence": img_result.get("confidence", "low")
            })
        
        state["current_results"] = display_data
        state["status"] = "waiting_approval"
        
        return True
        
    except Exception as e:
        log(f"Error: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        state["status"] = "idle"
        return False

def save_approved_batch(approved_data):
    """Save approved entries to database and delete image files."""
    state["status"] = "saving"
    conn = get_db_connection()
    cur = conn.cursor()
    
    saved_count = 0
    deleted_files = []
    
    for entry in approved_data.get('entries', []):
        if not entry.get('approved'):
            continue
        
        try:
            entry_id = str(uuid.uuid4())
            
            # Parse effective_date (format: YYYY/MM/DD)
            effective_date = entry.get('effective_date', '')
            if effective_date:
                try:
                    # Convert to PostgreSQL date format
                    parts = effective_date.split('/')
                    if len(parts) == 3:
                        effective_date = f"{parts[0]}-{parts[1]}-{parts[2]}"
                except:
                    effective_date = None
            else:
                effective_date = None
            
            cur.execute("""
                INSERT INTO documents_textentry 
                (id, title, text_type, content, effective_date, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                entry_id,
                entry.get('title', ''),
                entry.get('text_type', 'رای'),
                entry.get('content', ''),
                effective_date
            ))
            conn.commit()
            saved_count += 1
            log(f"Saved entry: {entry.get('title', '')[:50]}...")
            
            # Delete the image file
            img_file = entry.get('image_file')
            if img_file:
                img_path = os.path.join(state["jpg_dir"], img_file)
                if os.path.exists(img_path):
                    os.remove(img_path)
                    deleted_files.append(img_file)
                    log(f"Deleted image: {img_file}")
            
        except Exception as e:
            conn.rollback()
            log(f"Error saving entry: {e}")
    
    conn.close()
    state["processed_images"] += saved_count
    log(f"Saved {saved_count} entries, deleted {len(deleted_files)} files")
    state["status"] = "idle"
    
    return saved_count, deleted_files

# HTML Template
HTML = """
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>پردازشگر تصاویر اسناد حقوقی v1.0</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Vazirmatn', Tahoma, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 15px;
            min-height: 100vh;
            font-size: 13px;
        }
        .container { max-width: 1600px; margin: 0 auto; }
        h1 { text-align: center; color: #00d4ff; margin-bottom: 15px; font-size: 24px; font-weight: bold; }
        
        .stats {
            display: flex; gap: 15px; justify-content: center; margin-bottom: 15px;
        }
        .stat {
            background: rgba(0,212,255,0.1);
            border: 1px solid rgba(0,212,255,0.3);
            border-radius: 8px;
            padding: 10px 20px;
            text-align: center;
        }
        .stat-value { font-size: 20px; font-weight: bold; color: #00d4ff; }
        .stat-label { color: #aaa; font-size: 12px; }
        
        .controls { text-align: center; margin: 15px 0; }
        .btn {
            padding: 10px 25px;
            font-size: 14px;
            font-family: 'Vazirmatn', Tahoma, sans-serif;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            margin: 5px;
            transition: all 0.3s;
            font-weight: bold;
        }
        .btn-primary { background: linear-gradient(90deg, #00d4ff, #00ff88); color: #000; }
        .btn-success { background: #00ff88; color: #000; }
        .btn-danger { background: #ff4444; color: #fff; }
        .btn:hover { transform: scale(1.05); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        
        .status {
            text-align: center;
            padding: 10px;
            border-radius: 6px;
            margin: 10px 0;
            font-size: 14px;
            font-weight: bold;
        }
        .status-idle { background: rgba(100,100,100,0.3); }
        .status-processing { background: rgba(0,212,255,0.3); }
        .status-waiting { background: rgba(255,200,0,0.3); }
        
        .log-box {
            background: #0a0a15;
            border-radius: 6px;
            padding: 10px;
            max-height: 150px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 11px;
            margin-bottom: 15px;
        }
        
        .entry-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            display: grid;
            grid-template-columns: 300px 1fr;
            gap: 20px;
        }
        
        .image-preview {
            width: 100%;
            border-radius: 8px;
            border: 2px solid rgba(0,212,255,0.3);
        }
        
        .entry-form {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .form-label {
            color: #00d4ff;
            font-weight: bold;
            font-size: 13px;
        }
        
        .form-input, .form-textarea {
            background: rgba(0,0,0,0.4);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 6px;
            padding: 10px;
            color: #fff;
            font-family: 'Vazirmatn', Tahoma, sans-serif;
            font-size: 13px;
        }
        
        .form-textarea {
            min-height: 200px;
            resize: vertical;
        }
        
        .confidence-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        }
        .confidence-high { background: #00ff88; color: #000; }
        .confidence-medium { background: #ffcc00; color: #000; }
        .confidence-low { background: #ff4444; color: #fff; }
        
        .approve-checkbox {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            background: rgba(0,255,136,0.1);
            border-radius: 6px;
        }
        
        .approve-checkbox input[type="checkbox"] {
            width: 20px;
            height: 20px;
            cursor: pointer;
        }
        
        .approve-checkbox label {
            font-weight: bold;
            color: #00ff88;
            cursor: pointer;
        }
        
        #results { margin-top: 20px; }
        
        .batch-actions {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin: 20px 0;
            padding: 20px;
            background: rgba(0,212,255,0.1);
            border-radius: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🖼️ پردازشگر تصاویر اسناد حقوقی v{{ version }}</h1>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-value" id="total-images">0</div>
                <div class="stat-label">تصاویر باقیمانده</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="current-batch">0</div>
                <div class="stat-label">دسته فعلی</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="processed-images">0</div>
                <div class="stat-label">پردازش شده</div>
            </div>
        </div>
        
        <div class="status status-idle" id="status">آماده برای شروع</div>
        
        <div class="controls">
            <button class="btn btn-primary" id="btn-start" onclick="startProcessing()">شروع پردازش</button>
            <button class="btn btn-success" id="btn-approve" onclick="approveBatch()" style="display:none;">تأیید و ذخیره</button>
            <button class="btn btn-danger" id="btn-skip" onclick="skipBatch()" style="display:none;">رد کردن</button>
        </div>
        
        <div class="log-box" id="logs"></div>
        
        <div id="results"></div>
    </div>
    
    <script>
        let pollInterval = null;
        
        function updateUI(data) {
            document.getElementById('total-images').textContent = data.total_images;
            document.getElementById('current-batch').textContent = data.current_batch;
            document.getElementById('processed-images').textContent = data.processed_images;
            
            const statusDiv = document.getElementById('status');
            statusDiv.className = 'status';
            
            if (data.status === 'idle') {
                statusDiv.textContent = 'آماده';
                statusDiv.classList.add('status-idle');
                document.getElementById('btn-start').style.display = 'inline-block';
                document.getElementById('btn-approve').style.display = 'none';
                document.getElementById('btn-skip').style.display = 'none';
            } else if (data.status === 'processing') {
                statusDiv.textContent = '⏳ در حال پردازش...';
                statusDiv.classList.add('status-processing');
                document.getElementById('btn-start').style.display = 'none';
            } else if (data.status === 'waiting_approval') {
                statusDiv.textContent = '✅ آماده برای بررسی و تأیید';
                statusDiv.classList.add('status-waiting');
                document.getElementById('btn-start').style.display = 'none';
                document.getElementById('btn-approve').style.display = 'inline-block';
                document.getElementById('btn-skip').style.display = 'inline-block';
                showResults(data.current_results);
            }
            
            // Update logs
            const logsDiv = document.getElementById('logs');
            logsDiv.innerHTML = data.logs.slice(-10).map(l => `<div>${l}</div>`).join('');
            logsDiv.scrollTop = logsDiv.scrollHeight;
        }
        
        function showResults(results) {
            if (!results) return;
            
            const html = results.map((entry, idx) => `
                <div class="entry-card">
                    <div>
                        <img src="data:image/jpeg;base64,${entry.image_base64}" class="image-preview" alt="${entry.image_file}">
                        <div style="margin-top: 10px; text-align: center;">
                            <span class="confidence-badge confidence-${entry.confidence}">${entry.confidence}</span>
                            <div style="color: #aaa; font-size: 11px; margin-top: 5px;">${entry.image_file}</div>
                        </div>
                    </div>
                    <div class="entry-form">
                        <div class="approve-checkbox">
                            <input type="checkbox" id="approve-${idx}" checked>
                            <label for="approve-${idx}">تأیید و ذخیره این مورد</label>
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">عنوان:</label>
                            <input type="text" class="form-input" id="title-${idx}" value="${entry.title}">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">نوع متن:</label>
                            <input type="text" class="form-input" id="text_type-${idx}" value="${entry.text_type}">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">تاریخ شروع اعتبار (YYYY/MM/DD):</label>
                            <input type="text" class="form-input" id="effective_date-${idx}" value="${entry.effective_date}">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">محتوا:</label>
                            <textarea class="form-textarea" id="content-${idx}">${entry.content}</textarea>
                        </div>
                        
                        <input type="hidden" id="image_file-${idx}" value="${entry.image_file}">
                    </div>
                </div>
            `).join('');
            
            document.getElementById('results').innerHTML = html;
        }
        
        function startProcessing() {
            fetch('/api/start', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    updateUI(data);
                    startPolling();
                });
        }
        
        function approveBatch() {
            const results = document.querySelectorAll('.entry-card');
            const entries = [];
            
            results.forEach((card, idx) => {
                entries.push({
                    approved: document.getElementById(`approve-${idx}`).checked,
                    image_file: document.getElementById(`image_file-${idx}`).value,
                    title: document.getElementById(`title-${idx}`).value,
                    text_type: document.getElementById(`text_type-${idx}`).value,
                    content: document.getElementById(`content-${idx}`).value,
                    effective_date: document.getElementById(`effective_date-${idx}`).value
                });
            });
            
            fetch('/api/approve', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({entries: entries})
            })
            .then(r => r.json())
            .then(data => {
                updateUI(data);
                document.getElementById('results').innerHTML = '';
                // Continue processing next batch
                if (data.total_images > 0) {
                    setTimeout(() => startProcessing(), 1000);
                }
            });
        }
        
        function skipBatch() {
            fetch('/api/skip', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    updateUI(data);
                    document.getElementById('results').innerHTML = '';
                    // Continue processing next batch
                    if (data.total_images > 0) {
                        setTimeout(() => startProcessing(), 1000);
                    }
                });
        }
        
        function startPolling() {
            if (pollInterval) clearInterval(pollInterval);
            pollInterval = setInterval(() => {
                fetch('/api/status')
                    .then(r => r.json())
                    .then(data => {
                        updateUI(data);
                        if (data.status === 'idle' || data.status === 'waiting_approval') {
                            clearInterval(pollInterval);
                        }
                    });
            }, 1000);
        }
        
        // Initial load
        fetch('/api/status')
            .then(r => r.json())
            .then(data => updateUI(data));
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML, version=VERSION)

@app.route('/api/status')
def api_status():
    # Count remaining images
    all_images = get_jpg_images()
    state["total_images"] = len(all_images)
    
    return jsonify({
        "status": state["status"],
        "current_batch": state["current_batch"],
        "total_images": state["total_images"],
        "processed_images": state["processed_images"],
        "logs": state["logs"][-20:],
        "current_results": state["current_results"]
    })

@app.route('/api/start', methods=['POST'])
def api_start():
    if state["status"] != "idle":
        return jsonify({"error": "Already processing"}), 400
    
    # Count total images
    all_images = get_jpg_images()
    state["total_images"] = len(all_images)
    
    if state["total_images"] == 0:
        log("No JPG images found in directory!")
        return jsonify({
            "status": "idle",
            "current_batch": 0,
            "total_images": 0,
            "processed_images": state["processed_images"],
            "logs": state["logs"][-20:]
        })
    
    log(f"Found {state['total_images']} images to process")
    
    # Process first batch in background thread
    import threading
    threading.Thread(target=process_next_batch, daemon=True).start()
    
    return jsonify({
        "status": state["status"],
        "current_batch": state["current_batch"],
        "total_images": state["total_images"],
        "processed_images": state["processed_images"],
        "logs": state["logs"][-20:]
    })

@app.route('/api/approve', methods=['POST'])
def api_approve():
    if state["status"] != "waiting_approval":
        return jsonify({"error": "No batch waiting for approval"}), 400
    
    data = request.json
    
    # Save in background thread
    import threading
    threading.Thread(target=lambda: save_approved_batch(data), daemon=True).start()
    
    # Wait a bit for save to complete
    import time
    time.sleep(0.5)
    
    # Update image count
    all_images = get_jpg_images()
    state["total_images"] = len(all_images)
    
    return jsonify({
        "status": state["status"],
        "current_batch": state["current_batch"],
        "total_images": state["total_images"],
        "processed_images": state["processed_images"],
        "logs": state["logs"][-20:]
    })

@app.route('/api/skip', methods=['POST'])
def api_skip():
    if state["status"] != "waiting_approval":
        return jsonify({"error": "No batch waiting for approval"}), 400
    
    log(f"Skipped batch {state['current_batch']}")
    state["current_results"] = None
    state["status"] = "idle"
    
    # Update image count
    all_images = get_jpg_images()
    state["total_images"] = len(all_images)
    
    return jsonify({
        "status": state["status"],
        "current_batch": state["current_batch"],
        "total_images": state["total_images"],
        "processed_images": state["processed_images"],
        "logs": state["logs"][-20:]
    })

if __name__ == '__main__':
    log(f"AI Image Processor v{VERSION} starting...")
    log(f"Script directory: {state['script_dir']}")
    log(f"JPG directory: {state['jpg_dir']}")
    log(f"Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    log("Open http://localhost:5001 in your browser")
    
    app.run(host='0.0.0.0', port=5001, debug=False)
