#!/usr/bin/env python3
"""
Legal Unit Intelligent Tagger
=============================
A standalone tool for automatically tagging legal units using OpenAI GPT-4o-mini.

This tool:
1. Connects to the PostgreSQL database
2. Reads all vocabularies and vocabulary terms
3. Fetches untagged legal units in batches
4. Sends them to GPT-4o-mini for intelligent tagging
5. Saves the suggested tags back to the database

Usage:
1. Set your OpenAI API key and base URL below
2. Run: python legal_unit_tagger.py
3. Open http://localhost:5000 in your browser
"""

# ============================================
# CONFIGURATION - SET THESE VALUES
# ============================================
OPENAI_API_KEY = "sk-o92MoYgtEGcJrtvYEPS8t3BTWCwUfdg6o3HzdA67L3yWtddO"
OPENAI_BASE_URL = "https://api.gapgpt.app/v1"  # Or your custom endpoint

# Database connection (PostgreSQL on server)
# Port 15432 is exposed externally by docker-compose
DB_CONFIG = {
    "host": "45.92.219.229",  # Server IP (correct)
    "port": 15432,            # External port mapped to PostgreSQL
    "database": "ingest",
    "user": "ingest",
    "password": "rQXRweJEjVSD7tMKX4TrV3LQHDNhklt2"
}

# Model settings
MODEL_NAME = "gpt-4o-mini"
MAX_CONTEXT_TOKENS = 128000
# Batch size: با توجه به اینکه هر بند حدود 200-500 کاراکتر دارد
# و لیست برچسب‌ها حدود 30k توکن است، حدود 50-100 بند در هر batch مناسب است
BATCH_SIZE = 80  # Number of legal units per batch (adjust based on content length)

# ============================================
# DO NOT MODIFY BELOW THIS LINE
# ============================================

import json
import uuid
import threading
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI

app = Flask(__name__)

# Global state
processing_state = {
    "is_running": False,
    "current_batch": 0,
    "total_batches": 0,
    "processed_units": 0,
    "total_units": 0,
    "errors": [],
    "logs": [],
    "new_terms_suggested": []
}

def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        cursor_factory=RealDictCursor
    )

def log_message(message):
    """Add log message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    processing_state["logs"].append(f"[{timestamp}] {message}")
    print(f"[{timestamp}] {message}")

def get_vocabularies_and_terms():
    """Fetch all vocabularies and their terms from database."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get vocabularies
    cur.execute("""
        SELECT id, code, name 
        FROM masterdata_vocabulary 
        ORDER BY name
    """)
    vocabularies = cur.fetchall()
    
    # Get terms
    cur.execute("""
        SELECT vt.id, vt.code, vt.term, vt.vocabulary_id, v.name as vocabulary_name, v.code as vocabulary_code
        FROM masterdata_vocabularyterm vt
        JOIN masterdata_vocabulary v ON vt.vocabulary_id = v.id
        WHERE vt.is_active = true
        ORDER BY v.name, vt.term
    """)
    terms = cur.fetchall()
    
    conn.close()
    return vocabularies, terms

def get_untagged_legal_units(limit=300, offset=0):
    """Fetch legal units that don't have tags yet."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT lu.id, lu.path_label, lu.content, lu.unit_type
        FROM documents_legalunit lu
        WHERE lu.content IS NOT NULL 
          AND lu.content != ''
          AND NOT EXISTS (
              SELECT 1 FROM documents_legalunitvocabularyterm luvt 
              WHERE luvt.legal_unit_id = lu.id
          )
        ORDER BY lu.created_at
        LIMIT %s OFFSET %s
    """, (limit, offset))
    
    units = cur.fetchall()
    conn.close()
    return units

def count_untagged_legal_units():
    """Count total untagged legal units."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT COUNT(*) as count
        FROM documents_legalunit lu
        WHERE lu.content IS NOT NULL 
          AND lu.content != ''
          AND NOT EXISTS (
              SELECT 1 FROM documents_legalunitvocabularyterm luvt 
              WHERE luvt.legal_unit_id = lu.id
          )
    """)
    
    result = cur.fetchone()
    conn.close()
    return result["count"]

def build_prompt(terms, legal_units):
    """Build the prompt for GPT-4o-mini."""
    
    # Part 1: System instruction
    system_prompt = """شما یک متخصص حقوقی هستید که وظیفه برچسب‌گذاری بندهای حقوقی را دارید.

وظیفه شما:
1. برای هر بند حقوقی، برچسب‌های مرتبط را از لیست موجود انتخاب کنید
2. به هر برچسب وزنی بین 1 تا 10 بدهید (10 = بسیار مرتبط، 1 = کمی مرتبط)
3. حداکثر 20 برچسب برای هر بند انتخاب کنید
4. اگر بیش از 10 برچسب مرتبط پیدا کردید، فقط 10 برچسب با بالاترین وزن را نگه دارید
5. اگر برچسب مناسبی در لیست نیست، می‌توانید برچسب جدید پیشنهاد دهید

فرمت خروجی (JSON):
{
  "tagged_units": [
    {
      "unit_id": "uuid-of-unit",
      "tags": [
        {"term_id": "uuid-of-term", "weight": 8},
        {"term_id": "uuid-of-term", "weight": 6}
      ]
    }
  ],
  "suggested_new_terms": [
    {
      "vocabulary_code": "existing-vocab-code",
      "term": "اصطلاح جدید",
      "code": "NewTerm.code"
    }
  ]
}

نکات مهم:
- فقط JSON خالص برگردانید، بدون هیچ توضیح اضافی
- term_id باید دقیقاً UUID برچسب از جدول زیر باشد
- برای برچسب‌های پیشنهادی جدید، vocabulary_code باید از موضوعات موجود باشد"""

    # Part 2: Terms table
    terms_table = "## لیست برچسب‌های موجود:\n\n"
    terms_table += "| UUID | موضوع | برچسب | کد |\n"
    terms_table += "|------|-------|-------|-----|\n"
    
    for term in terms:
        terms_table += f"| {term['id']} | {term['vocabulary_name']} | {term['term']} | {term['code']} |\n"
    
    # Part 3: Legal units to tag
    units_section = "\n\n## بندهای حقوقی برای برچسب‌گذاری:\n\n"
    
    for unit in legal_units:
        content = unit['content'][:500] if len(unit['content']) > 500 else unit['content']
        units_section += f"### بند: {unit['id']}\n"
        units_section += f"**مسیر:** {unit['path_label']}\n"
        units_section += f"**نوع:** {unit['unit_type']}\n"
        units_section += f"**محتوا:** {content}\n\n"
        units_section += "---\n\n"
    
    return system_prompt, terms_table + units_section

def call_openai(system_prompt, user_prompt):
    """Call OpenAI API."""
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL
    )
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        response_format={"type": "json_object"}
    )
    
    return response.choices[0].message.content

def is_valid_uuid(val):
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError):
        return False

def save_tags_to_database(tagged_units, new_terms, valid_term_ids):
    """Save tags and new terms to database.
    
    Args:
        tagged_units: List of units with their tags from GPT
        new_terms: List of new term suggestions from GPT
        valid_term_ids: Set of valid term UUIDs from database
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    saved_tags = 0
    saved_terms = 0
    skipped_invalid = 0
    
    # First, save any new suggested terms
    for term in new_terms:
        try:
            # Get vocabulary ID
            cur.execute("""
                SELECT id FROM masterdata_vocabulary WHERE code = %s
            """, (term.get("vocabulary_code"),))
            vocab = cur.fetchone()
            
            if vocab:
                term_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO masterdata_vocabularyterm (id, vocabulary_id, term, code, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, true, NOW(), NOW())
                    ON CONFLICT DO NOTHING
                """, (term_id, vocab["id"], term.get("term"), term.get("code")))
                conn.commit()  # Commit each term separately
                saved_terms += 1
                processing_state["new_terms_suggested"].append(term)
        except Exception as e:
            conn.rollback()  # Rollback on error
            log_message(f"Error saving new term: {e}")
    
    # Save tags for each unit
    for unit in tagged_units:
        unit_id = unit.get("unit_id")
        tags = unit.get("tags", [])
        
        # Validate unit_id
        if not is_valid_uuid(unit_id):
            skipped_invalid += 1
            continue
        
        for tag in tags:
            term_id = tag.get("term_id")
            
            # Validate term_id format
            if not is_valid_uuid(term_id):
                skipped_invalid += 1
                continue
            
            # Check if term_id exists in our valid set
            if str(term_id) not in valid_term_ids:
                skipped_invalid += 1
                continue
            
            try:
                weight = min(max(int(tag.get("weight", 5)), 1), 10)  # Clamp 1-10
                
                tag_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO documents_legalunitvocabularyterm 
                    (id, legal_unit_id, vocabulary_term_id, weight, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (legal_unit_id, vocabulary_term_id) DO UPDATE SET weight = %s, updated_at = NOW()
                """, (tag_id, unit_id, term_id, weight, weight))
                conn.commit()  # Commit each tag separately to avoid transaction issues
                saved_tags += 1
            except Exception as e:
                conn.rollback()  # Rollback on error
                log_message(f"Error saving tag for unit {unit_id}: {e}")
    
    conn.close()
    
    if skipped_invalid > 0:
        log_message(f"Skipped {skipped_invalid} invalid/non-existent term IDs")
    
    return saved_tags, saved_terms

def process_batch(batch_num, terms, valid_term_ids):
    """Process a single batch of legal units.
    
    Args:
        batch_num: Current batch number
        terms: List of vocabulary terms for the prompt
        valid_term_ids: Set of valid term UUIDs
    """
    try:
        # Get legal units for this batch
        units = get_untagged_legal_units(limit=BATCH_SIZE, offset=0)  # Always offset 0 since we're processing untagged
        
        if not units:
            log_message(f"Batch {batch_num}: No more untagged units")
            return False
        
        log_message(f"Batch {batch_num}: Processing {len(units)} units...")
        
        # Build prompt
        system_prompt, user_prompt = build_prompt(terms, units)
        
        # Call OpenAI
        log_message(f"Batch {batch_num}: Calling OpenAI API...")
        response = call_openai(system_prompt, user_prompt)
        
        # Parse response
        try:
            result = json.loads(response)
            tagged_units = result.get("tagged_units", [])
            new_terms = result.get("suggested_new_terms", [])
            
            log_message(f"Batch {batch_num}: Got {len(tagged_units)} tagged units, {len(new_terms)} new term suggestions")
            
            # Save to database with validation
            saved_tags, saved_terms = save_tags_to_database(tagged_units, new_terms, valid_term_ids)
            log_message(f"Batch {batch_num}: Saved {saved_tags} tags, {saved_terms} new terms")
            
            processing_state["processed_units"] += len(units)
            
        except json.JSONDecodeError as e:
            log_message(f"Batch {batch_num}: JSON parse error: {e}")
            processing_state["errors"].append(f"Batch {batch_num}: JSON parse error")
        
        return True
        
    except Exception as e:
        log_message(f"Batch {batch_num}: Error: {e}")
        processing_state["errors"].append(f"Batch {batch_num}: {str(e)}")
        return False

def run_tagging_process():
    """Main tagging process."""
    processing_state["is_running"] = True
    processing_state["errors"] = []
    processing_state["logs"] = []
    processing_state["new_terms_suggested"] = []
    
    try:
        # Get vocabularies and terms
        log_message("Loading vocabularies and terms...")
        vocabularies, terms = get_vocabularies_and_terms()
        log_message(f"Loaded {len(vocabularies)} vocabularies, {len(terms)} terms")
        
        # Build set of valid term IDs for validation
        valid_term_ids = {str(t['id']) for t in terms}
        log_message(f"Built validation set with {len(valid_term_ids)} valid term IDs")
        
        # Count untagged units
        total_untagged = count_untagged_legal_units()
        processing_state["total_units"] = total_untagged
        processing_state["total_batches"] = (total_untagged + BATCH_SIZE - 1) // BATCH_SIZE
        
        log_message(f"Found {total_untagged} untagged legal units ({processing_state['total_batches']} batches)")
        
        # Process batches
        batch_num = 1
        while processing_state["is_running"]:
            processing_state["current_batch"] = batch_num
            
            if not process_batch(batch_num, terms, valid_term_ids):
                break
            
            batch_num += 1
            
            # Check if we've processed all
            remaining = count_untagged_legal_units()
            if remaining == 0:
                log_message("All units have been tagged!")
                break
        
        log_message("Tagging process completed!")
        
    except Exception as e:
        log_message(f"Fatal error: {e}")
        processing_state["errors"].append(f"Fatal: {str(e)}")
    
    processing_state["is_running"] = False

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>برچسب‌گذار هوشمند بندهای حقوقی</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: 'Vazirmatn', 'Tahoma', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            color: #00d4ff;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-box {
            background: rgba(0,212,255,0.1);
            border: 1px solid rgba(0,212,255,0.3);
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }
        .stat-value {
            font-size: 2.5em;
            font-weight: bold;
            color: #00d4ff;
        }
        .stat-label {
            color: #aaa;
            margin-top: 5px;
        }
        .progress-bar {
            width: 100%;
            height: 30px;
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            overflow: hidden;
            margin: 20px 0;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #000;
            font-weight: bold;
        }
        .btn {
            padding: 15px 40px;
            font-size: 1.2em;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
            margin: 5px;
        }
        .btn-start {
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            color: #000;
        }
        .btn-stop {
            background: linear-gradient(90deg, #ff4444, #ff8800);
            color: #fff;
        }
        .btn:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 20px rgba(0,212,255,0.4);
        }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .log-container {
            background: #0a0a15;
            border-radius: 10px;
            padding: 15px;
            max-height: 400px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.9em;
        }
        .log-entry {
            padding: 5px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .error { color: #ff4444; }
        .success { color: #00ff88; }
        .controls {
            text-align: center;
            margin: 30px 0;
        }
        .status-indicator {
            display: inline-block;
            width: 15px;
            height: 15px;
            border-radius: 50%;
            margin-left: 10px;
            animation: pulse 1.5s infinite;
        }
        .status-running { background: #00ff88; }
        .status-stopped { background: #ff4444; animation: none; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .new-terms {
            margin-top: 20px;
        }
        .term-badge {
            display: inline-block;
            background: rgba(0,255,136,0.2);
            border: 1px solid #00ff88;
            border-radius: 20px;
            padding: 5px 15px;
            margin: 5px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏷️ برچسب‌گذار هوشمند بندهای حقوقی</h1>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-value" id="total-units">-</div>
                <div class="stat-label">کل بندهای بدون برچسب</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="processed-units">0</div>
                <div class="stat-label">بندهای پردازش شده</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="current-batch">0</div>
                <div class="stat-label">دسته فعلی</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="total-batches">-</div>
                <div class="stat-label">کل دسته‌ها</div>
            </div>
        </div>
        
        <div class="card">
            <h3>پیشرفت</h3>
            <div class="progress-bar">
                <div class="progress-fill" id="progress" style="width: 0%">0%</div>
            </div>
        </div>
        
        <div class="controls">
            <span class="status-indicator status-stopped" id="status-indicator"></span>
            <span id="status-text">متوقف</span>
            <br><br>
            <button class="btn btn-start" id="btn-start" onclick="startProcess()">🚀 شروع برچسب‌گذاری</button>
            <button class="btn btn-stop" id="btn-stop" onclick="stopProcess()" disabled>⏹️ توقف</button>
        </div>
        
        <div class="card">
            <h3>📝 گزارش عملیات</h3>
            <div class="log-container" id="log-container">
                <div class="log-entry">در انتظار شروع...</div>
            </div>
        </div>
        
        <div class="card new-terms" id="new-terms-section" style="display:none;">
            <h3>🆕 برچسب‌های جدید پیشنهادی</h3>
            <div id="new-terms-container"></div>
        </div>
    </div>
    
    <script>
        let updateInterval;
        
        function startProcess() {
            fetch('/start', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('btn-start').disabled = true;
                        document.getElementById('btn-stop').disabled = false;
                        document.getElementById('status-indicator').className = 'status-indicator status-running';
                        document.getElementById('status-text').textContent = 'در حال اجرا...';
                        updateInterval = setInterval(updateStatus, 2000);
                    }
                });
        }
        
        function stopProcess() {
            fetch('/stop', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    document.getElementById('btn-start').disabled = false;
                    document.getElementById('btn-stop').disabled = true;
                    document.getElementById('status-indicator').className = 'status-indicator status-stopped';
                    document.getElementById('status-text').textContent = 'متوقف شد';
                    clearInterval(updateInterval);
                });
        }
        
        function updateStatus() {
            fetch('/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('total-units').textContent = data.total_units || '-';
                    document.getElementById('processed-units').textContent = data.processed_units;
                    document.getElementById('current-batch').textContent = data.current_batch;
                    document.getElementById('total-batches').textContent = data.total_batches || '-';
                    
                    // Progress
                    let progress = 0;
                    if (data.total_units > 0) {
                        progress = Math.round((data.processed_units / data.total_units) * 100);
                    }
                    document.getElementById('progress').style.width = progress + '%';
                    document.getElementById('progress').textContent = progress + '%';
                    
                    // Logs
                    const logContainer = document.getElementById('log-container');
                    logContainer.innerHTML = data.logs.map(log => 
                        `<div class="log-entry">${log}</div>`
                    ).join('');
                    logContainer.scrollTop = logContainer.scrollHeight;
                    
                    // New terms
                    if (data.new_terms_suggested && data.new_terms_suggested.length > 0) {
                        document.getElementById('new-terms-section').style.display = 'block';
                        document.getElementById('new-terms-container').innerHTML = 
                            data.new_terms_suggested.map(t => 
                                `<span class="term-badge">${t.term} (${t.vocabulary_code})</span>`
                            ).join('');
                    }
                    
                    // Check if stopped
                    if (!data.is_running) {
                        document.getElementById('btn-start').disabled = false;
                        document.getElementById('btn-stop').disabled = true;
                        document.getElementById('status-indicator').className = 'status-indicator status-stopped';
                        document.getElementById('status-text').textContent = 'تکمیل شد';
                        clearInterval(updateInterval);
                    }
                });
        }
        
        // Initial status check
        updateStatus();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/status')
def status():
    return jsonify(processing_state)

@app.route('/start', methods=['POST'])
def start():
    if not processing_state["is_running"]:
        thread = threading.Thread(target=run_tagging_process)
        thread.daemon = True
        thread.start()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Already running"})

@app.route('/stop', methods=['POST'])
def stop():
    processing_state["is_running"] = False
    return jsonify({"success": True})

if __name__ == '__main__':
    print("=" * 60)
    print("Legal Unit Intelligent Tagger")
    print("=" * 60)
    print(f"OpenAI Base URL: {OPENAI_BASE_URL}")
    print(f"Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    print(f"Model: {MODEL_NAME}")
    print(f"Batch Size: {BATCH_SIZE}")
    print("=" * 60)
    print("Starting web server at http://localhost:5000")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
