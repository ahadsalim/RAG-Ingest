#!/usr/bin/env python3
"""
Legal Unit Intelligent Tagger v2
================================
Interactive tool for tagging legal units using OpenAI GPT-4o-mini.
Shows a table for each batch with unit content, existing tags, and suggested tags.
User must approve each batch before saving.

Usage:
1. Set your OpenAI API key and base URL below
2. Run: python legal_unit_tagger_v2.py
3. Open http://localhost:5000 in your browser
"""

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
MODEL_NAME = "gpt-4o-mini"
BATCH_SIZE = 30  # Smaller batch for better review

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
state = {
    "status": "idle",  # idle, processing, waiting_approval, saving
    "current_batch": 0,
    "total_batches": 0,
    "total_units": 0,
    "processed_units": 0,
    "logs": [],
    "vocabularies": [],
    "terms": [],
    "valid_term_ids": set(),
    "term_lookup": {},  # id -> term info
    "current_results": None,  # Current batch results waiting for approval
    "current_units": None,  # Current batch units
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
    state["logs"].append(f"[{ts}] {msg}")
    print(f"[{ts}] {msg}")

def load_vocabularies_and_terms():
    """Load all vocabularies and terms from database."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id, code, name FROM masterdata_vocabulary ORDER BY name")
    state["vocabularies"] = list(cur.fetchall())
    
    cur.execute("""
        SELECT vt.id, vt.code, vt.term, vt.vocabulary_id, 
               v.name as vocabulary_name, v.code as vocabulary_code
        FROM masterdata_vocabularyterm vt
        JOIN masterdata_vocabulary v ON vt.vocabulary_id = v.id
        WHERE vt.is_active = true
        ORDER BY v.name, vt.term
    """)
    state["terms"] = list(cur.fetchall())
    state["valid_term_ids"] = {str(t['id']) for t in state["terms"]}
    state["term_lookup"] = {str(t['id']): t for t in state["terms"]}
    
    conn.close()
    log(f"Loaded {len(state['vocabularies'])} vocabularies, {len(state['terms'])} terms")

def get_untagged_units(limit=30):
    """Get untagged legal units."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT lu.id, lu.path_label, lu.content, lu.unit_type
        FROM documents_legalunit lu
        WHERE lu.content IS NOT NULL AND lu.content != ''
          AND NOT EXISTS (
              SELECT 1 FROM documents_legalunitvocabularyterm luvt 
              WHERE luvt.legal_unit_id = lu.id
          )
        ORDER BY lu.created_at
        LIMIT %s
    """, (limit,))
    
    units = list(cur.fetchall())
    conn.close()
    return units

def get_existing_tags(unit_ids):
    """Get existing tags for units."""
    if not unit_ids:
        return {}
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    placeholders = ','.join(['%s'] * len(unit_ids))
    cur.execute(f"""
        SELECT luvt.legal_unit_id, luvt.vocabulary_term_id, luvt.weight,
               vt.term, v.name as vocabulary_name
        FROM documents_legalunitvocabularyterm luvt
        JOIN masterdata_vocabularyterm vt ON luvt.vocabulary_term_id = vt.id
        JOIN masterdata_vocabulary v ON vt.vocabulary_id = v.id
        WHERE luvt.legal_unit_id IN ({placeholders})
    """, unit_ids)
    
    result = {}
    for row in cur.fetchall():
        uid = str(row['legal_unit_id'])
        if uid not in result:
            result[uid] = []
        result[uid].append({
            'term_id': str(row['vocabulary_term_id']),
            'term': row['term'],
            'vocabulary': row['vocabulary_name'],
            'weight': row['weight']
        })
    
    conn.close()
    return result

def count_untagged():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) as count FROM documents_legalunit lu
        WHERE lu.content IS NOT NULL AND lu.content != ''
          AND NOT EXISTS (
              SELECT 1 FROM documents_legalunitvocabularyterm luvt 
              WHERE luvt.legal_unit_id = lu.id
          )
    """)
    result = cur.fetchone()
    conn.close()
    return result["count"]

def build_prompt(units):
    """Build prompt for GPT based on Legal Tagging Engine template."""
    
    system = """تو یک Legal Tagging Engine هستی که باید برای هر «بند قانون» برچسب‌گذاری دقیق انجام دهی تا در Hybrid RAG Search (semantic + keyword) استفاده شود.

## وظایف تو:
1. از بین existing_tags فقط برچسب‌هایی را انتخاب کن که **مستقیماً و مفهومی** با بند مرتبط هستند.
2. به هر برچسب انتخاب‌شده یک وزن عددی بین 1 تا 10 بده.
3. اگر تعداد برچسب‌های انتخاب‌شده بیش از 10 بود:
   - فقط 10 برچسب با بیشترین وزن را نگه دار
   - بقیه را حذف کن
4. در هیچ حالتی مجموع برچسب‌های نهایی نباید بیش از 20 باشد.
5. اگر بند شامل مفاهیم مهمی است که در existing_tags نیست:
   - برچسب جدید پیشنهاد بده
   - این برچسب‌ها باید: کوتاه (۱ تا ۳ کلمه)، نرمال‌شده (بدون فعل، بدون جمع، بدون ابهام)، مناسب استفاده مکرر در کل دیتابیس
   - برچسب‌های پیشنهادی جدید را در new_tags خروجی بده و در برچسب‌های همین بند هم لحاظ کن

## قواعد مهم:
- برچسب‌ها باید حقوقی، مفهومی و پایدار باشند (نه جمله، نه توصیفی)
- وزن = میزان اهمیت آن برچسب برای بازیابی این بند در جستجو
- وزن‌ها نسبی‌اند، نه مساوی
- از برچسب خیلی خاصِ تک‌مصرف اجتناب کن

## راهنمای وزن‌دهی:
- هسته اصلی بند → 9 تا 10
- موضوع مهم فرعی → 6 تا 8  
- وابسته یا تلویحی → 3 تا 5

## فرمت خروجی (فقط JSON خالص، بدون هیچ متن اضافه):
{
  "results": [
    {
      "unit_id": "uuid-of-unit",
      "final_tags": [
        {"term_id": "uuid-of-existing-tag", "tag": "نام برچسب", "weight": 9}
      ],
      "new_tags": [
        {"tag": "برچسب جدید پیشنهادی", "weight": 7, "vocabulary_code": "کد-موضوع-مرتبط"}
      ]
    }
  ]
}

نکته: term_id باید دقیقاً UUID برچسب از جدول existing_tags باشد."""

    # Build existing tags list
    tags_list = "## existing_tags (برچسب‌های موجود در دیتابیس):\n\n"
    tags_list += "| term_id (UUID) | موضوع (vocabulary) | برچسب (tag) |\n"
    tags_list += "|----------------|-------------------|-------------|\n"
    for t in state["terms"]:
        tags_list += f"| {t['id']} | {t['vocabulary_name']} | {t['term']} |\n"
    
    # Build units/clauses
    clauses = "\n\n## بندهای قانون برای برچسب‌گذاری:\n"
    for u in units:
        content = u['content']
        clauses += f"\n### unit_id: {u['id']}\n"
        clauses += f"**مسیر:** {u['path_label']}\n"
        clauses += f"**نوع:** {u['unit_type']}\n"
        clauses += f"**clause_text:**\n{content}\n"
        clauses += "\n---\n"
    
    user_prompt = tags_list + clauses
    
    return system, user_prompt

def save_prompt_to_file(batch_num, system, user):
    """Save prompt to file for debugging."""
    import os
    debug_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(debug_dir, f"batch{batch_num}_prompt.txt")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("SYSTEM PROMPT:\n")
        f.write("=" * 80 + "\n")
        f.write(system)
        f.write("\n\n")
        f.write("=" * 80 + "\n")
        f.write("USER PROMPT:\n")
        f.write("=" * 80 + "\n")
        f.write(user)
    
    return filename

def call_gpt(system, user):
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        temperature=0.3,
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except:
        return False

def process_next_batch():
    """Process next batch and prepare for approval."""
    state["status"] = "processing"
    state["current_batch"] += 1
    
    log(f"Batch {state['current_batch']}: Loading units...")
    units = get_untagged_units(BATCH_SIZE)
    
    if not units:
        log("No more untagged units!")
        state["status"] = "idle"
        return False
    
    state["current_units"] = units
    unit_ids = [str(u['id']) for u in units]
    existing_tags = get_existing_tags(unit_ids)
    
    log(f"Batch {state['current_batch']}: Calling GPT for {len(units)} units...")
    
    try:
        system, user = build_prompt(units)
        
        # Save prompt to file for debugging
        prompt_file = save_prompt_to_file(state['current_batch'], system, user)
        log(f"Batch {state['current_batch']}: Prompt saved to {prompt_file}")
        
        response = call_gpt(system, user)
        
        # Save response to file for debugging
        import os
        debug_dir = os.path.dirname(os.path.abspath(__file__))
        response_file = os.path.join(debug_dir, f"batch{state['current_batch']}_response.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            f.write(response)
        log(f"Batch {state['current_batch']}: Response saved to {response_file}")
        
        result = json.loads(response)
        
        # New format: results array with final_tags and new_tags per unit
        results = result.get("results", [])
        
        log(f"Batch {state['current_batch']}: Got {len(results)} unit results")
        
        # Collect all new tags from all units
        all_new_terms = []
        
        # Build display data
        display_data = []
        for unit in units:
            uid = str(unit['id'])
            unit_result = next((r for r in results if r.get('unit_id') == uid), None)
            
            suggested_tags = []
            unit_new_tags = []
            
            if unit_result:
                # Process final_tags (existing tags from database)
                for tag in unit_result.get('final_tags', []):
                    tid = tag.get('term_id')
                    if is_valid_uuid(tid) and tid in state["term_lookup"]:
                        term_info = state["term_lookup"][tid]
                        suggested_tags.append({
                            'term_id': tid,
                            'term': term_info['term'],
                            'vocabulary': term_info['vocabulary_name'],
                            'weight': tag.get('weight', 5),
                            'valid': True,
                            'is_new': False
                        })
                    else:
                        suggested_tags.append({
                            'term_id': tid,
                            'term': tag.get('tag', '❌ نامعتبر'),
                            'vocabulary': '-',
                            'weight': tag.get('weight', 5),
                            'valid': False,
                            'is_new': False
                        })
                
                # Process new_tags (suggested new terms)
                for new_tag in unit_result.get('new_tags', []):
                    unit_new_tags.append({
                        'tag': new_tag.get('tag'),
                        'weight': new_tag.get('weight', 5),
                        'vocabulary_code': new_tag.get('vocabulary_code', ''),
                        'unit_id': uid
                    })
                    # Also add to suggested_tags for display
                    suggested_tags.append({
                        'term_id': None,
                        'term': f"🆕 {new_tag.get('tag')}",
                        'vocabulary': new_tag.get('vocabulary_code', 'جدید'),
                        'weight': new_tag.get('weight', 5),
                        'valid': True,
                        'is_new': True,
                        'new_tag_data': new_tag
                    })
                
                all_new_terms.extend(unit_new_tags)
            
            display_data.append({
                'unit_id': uid,
                'path_label': unit['path_label'],
                'unit_type': unit['unit_type'],
                'content': unit['content'],
                'existing_tags': existing_tags.get(uid, []),
                'suggested_tags': suggested_tags
            })
        
        state["current_results"] = {
            'units': display_data,
            'new_terms': all_new_terms,
            'raw_results': results
        }
        state["status"] = "waiting_approval"
        
        return True
        
    except Exception as e:
        log(f"Error: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        state["status"] = "idle"
        return False

def save_approved_batch(approved_data):
    """Save approved tags to database."""
    state["status"] = "saving"
    conn = get_db_connection()
    cur = conn.cursor()
    
    saved_tags = 0
    saved_terms = 0
    
    # Save new terms first
    for term in approved_data.get('new_terms', []):
        if not term.get('approved'):
            continue
        try:
            vocab_code = term.get('vocabulary_code', '')
            cur.execute("SELECT id FROM masterdata_vocabulary WHERE code = %s", (vocab_code,))
            vocab = cur.fetchone()
            if vocab:
                term_id = str(uuid.uuid4())
                tag_name = term.get('tag', term.get('term', ''))
                # Generate code from tag name (remove spaces, use CamelCase)
                tag_code = ''.join(word.capitalize() for word in tag_name.split())
                cur.execute("""
                    INSERT INTO masterdata_vocabularyterm (id, vocabulary_id, term, code, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, true, NOW(), NOW())
                    ON CONFLICT DO NOTHING
                """, (term_id, vocab['id'], tag_name, tag_code))
                conn.commit()
                saved_terms += 1
                # Add to valid terms
                state["valid_term_ids"].add(term_id)
                log(f"Added new term: {tag_name} to {vocab_code}")
            else:
                log(f"Vocabulary not found: {vocab_code}")
        except Exception as e:
            conn.rollback()
            log(f"Error saving term: {e}")
    
    # Save tags
    for unit in approved_data.get('units', []):
        unit_id = unit['unit_id']
        for tag in unit.get('tags', []):
            if not tag.get('approved'):
                continue
            term_id = tag['term_id']
            weight = tag.get('weight', 5)
            
            if not is_valid_uuid(term_id) or term_id not in state["valid_term_ids"]:
                continue
            
            try:
                tag_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO documents_legalunitvocabularyterm 
                    (id, legal_unit_id, vocabulary_term_id, weight, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (legal_unit_id, vocabulary_term_id) DO UPDATE SET weight = %s, updated_at = NOW()
                """, (tag_id, unit_id, term_id, weight, weight))
                conn.commit()
                saved_tags += 1
            except Exception as e:
                conn.rollback()
                log(f"Error saving tag: {e}")
    
    conn.close()
    state["processed_units"] += len(approved_data.get('units', []))
    log(f"Saved {saved_tags} tags, {saved_terms} new terms")
    state["status"] = "idle"
    
    return saved_tags, saved_terms

# HTML Template
HTML = """
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>برچسب‌گذار هوشمند v2</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Vazirmatn', Tahoma, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { text-align: center; color: #00d4ff; margin-bottom: 20px; }
        
        .stats {
            display: flex; gap: 20px; justify-content: center; margin-bottom: 20px;
        }
        .stat {
            background: rgba(0,212,255,0.1);
            border: 1px solid rgba(0,212,255,0.3);
            border-radius: 10px;
            padding: 15px 25px;
            text-align: center;
        }
        .stat-value { font-size: 2em; font-weight: bold; color: #00d4ff; }
        .stat-label { color: #aaa; font-size: 0.9em; }
        
        .controls { text-align: center; margin: 20px 0; }
        .btn {
            padding: 12px 30px;
            font-size: 1.1em;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            margin: 5px;
            transition: all 0.3s;
        }
        .btn-primary { background: linear-gradient(90deg, #00d4ff, #00ff88); color: #000; }
        .btn-success { background: #00ff88; color: #000; }
        .btn-danger { background: #ff4444; color: #fff; }
        .btn:hover { transform: scale(1.05); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        
        .status {
            text-align: center;
            padding: 10px;
            border-radius: 8px;
            margin: 10px 0;
        }
        .status-idle { background: rgba(100,100,100,0.3); }
        .status-processing { background: rgba(0,212,255,0.3); }
        .status-waiting { background: rgba(255,200,0,0.3); }
        
        .log-box {
            background: #0a0a15;
            border-radius: 8px;
            padding: 15px;
            max-height: 150px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.85em;
            margin-bottom: 20px;
        }
        
        .unit-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .unit-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .unit-path { color: #00d4ff; font-weight: bold; }
        .unit-type { 
            background: rgba(0,212,255,0.2);
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 0.85em;
        }
        .unit-content {
            background: rgba(0,0,0,0.3);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            line-height: 1.8;
            max-height: 150px;
            overflow-y: auto;
        }
        
        .tags-section { margin-top: 15px; }
        .tags-title { 
            font-weight: bold; 
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .tags-title .icon { font-size: 1.2em; }
        
        .tag-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }
        .tag-table th, .tag-table td {
            padding: 8px 12px;
            text-align: right;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .tag-table th {
            background: rgba(0,212,255,0.1);
            color: #00d4ff;
        }
        .tag-table tr:hover { background: rgba(255,255,255,0.05); }
        
        .tag-existing { color: #888; }
        .tag-new { color: #00ff88; }
        .tag-invalid { color: #ff4444; text-decoration: line-through; }
        
        .weight-badge {
            display: inline-block;
            width: 30px;
            height: 30px;
            line-height: 30px;
            text-align: center;
            border-radius: 50%;
            font-weight: bold;
        }
        .weight-high { background: #00ff88; color: #000; }
        .weight-mid { background: #ffcc00; color: #000; }
        .weight-low { background: #ff8844; color: #000; }
        
        .checkbox-cell { width: 40px; text-align: center; }
        .checkbox-cell input { width: 18px; height: 18px; cursor: pointer; }
        
        .new-terms-section {
            background: rgba(0,255,136,0.1);
            border: 1px solid rgba(0,255,136,0.3);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .new-terms-title { color: #00ff88; margin-bottom: 15px; }
        
        .hidden { display: none; }
        
        .loading {
            text-align: center;
            padding: 50px;
            font-size: 1.5em;
            color: #00d4ff;
        }
        .loading::after {
            content: '';
            animation: dots 1.5s infinite;
        }
        @keyframes dots {
            0%, 20% { content: '.'; }
            40% { content: '..'; }
            60%, 100% { content: '...'; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏷️ برچسب‌گذار هوشمند بندهای حقوقی</h1>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-value" id="total-units">-</div>
                <div class="stat-label">کل بندهای بدون برچسب</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="processed">0</div>
                <div class="stat-label">پردازش شده</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="current-batch">0</div>
                <div class="stat-label">دسته فعلی</div>
            </div>
        </div>
        
        <div class="status status-idle" id="status-box">
            <span id="status-text">آماده شروع</span>
        </div>
        
        <div class="controls" id="main-controls">
            <button class="btn btn-primary" id="btn-start" onclick="startProcess()">
                🚀 شروع برچسب‌گذاری
            </button>
        </div>
        
        <div class="log-box" id="log-box"></div>
        
        <div id="results-section" class="hidden">
            <!-- New terms section -->
            <div id="new-terms-section" class="new-terms-section hidden">
                <h3 class="new-terms-title">🆕 برچسب‌های جدید پیشنهادی</h3>
                <table class="tag-table">
                    <thead>
                        <tr>
                            <th class="checkbox-cell">✓</th>
                            <th>موضوع</th>
                            <th>برچسب</th>
                            <th>کد</th>
                        </tr>
                    </thead>
                    <tbody id="new-terms-body"></tbody>
                </table>
            </div>
            
            <!-- Units section -->
            <div id="units-container"></div>
            
            <div class="controls">
                <button class="btn btn-success" onclick="approveAll()">✅ تأیید همه و ذخیره</button>
                <button class="btn btn-primary" onclick="approveSelected()">💾 ذخیره انتخاب‌شده‌ها</button>
                <button class="btn btn-danger" onclick="skipBatch()">⏭️ رد کردن این دسته</button>
            </div>
        </div>
        
        <div id="loading-section" class="hidden">
            <div class="loading">در حال پردازش با هوش مصنوعی</div>
        </div>
    </div>
    
    <script>
        let currentData = null;
        
        function updateStatus() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('total-units').textContent = data.total_units || '-';
                    document.getElementById('processed').textContent = data.processed_units;
                    document.getElementById('current-batch').textContent = data.current_batch;
                    
                    // Logs
                    document.getElementById('log-box').innerHTML = 
                        data.logs.slice(-20).map(l => `<div>${l}</div>`).join('');
                    
                    // Status
                    const statusBox = document.getElementById('status-box');
                    const statusText = document.getElementById('status-text');
                    statusBox.className = 'status';
                    
                    if (data.status === 'idle') {
                        statusBox.classList.add('status-idle');
                        statusText.textContent = 'آماده';
                        document.getElementById('btn-start').disabled = false;
                    } else if (data.status === 'processing') {
                        statusBox.classList.add('status-processing');
                        statusText.textContent = 'در حال پردازش...';
                        document.getElementById('btn-start').disabled = true;
                    } else if (data.status === 'waiting_approval') {
                        statusBox.classList.add('status-waiting');
                        statusText.textContent = 'منتظر تأیید شما';
                        loadResults();
                    }
                });
        }
        
        function startProcess() {
            document.getElementById('btn-start').disabled = true;
            document.getElementById('results-section').classList.add('hidden');
            document.getElementById('loading-section').classList.remove('hidden');
            
            fetch('/api/start', {method: 'POST'})
                .then(r => r.json())
                .then(() => {
                    pollForResults();
                });
        }
        
        function pollForResults() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    updateStatus();
                    if (data.status === 'waiting_approval') {
                        document.getElementById('loading-section').classList.add('hidden');
                        loadResults();
                    } else if (data.status === 'processing') {
                        setTimeout(pollForResults, 2000);
                    } else {
                        document.getElementById('loading-section').classList.add('hidden');
                    }
                });
        }
        
        function loadResults() {
            fetch('/api/results')
                .then(r => r.json())
                .then(data => {
                    currentData = data;
                    renderResults(data);
                    document.getElementById('results-section').classList.remove('hidden');
                });
        }
        
        function renderResults(data) {
            // New terms
            const newTermsSection = document.getElementById('new-terms-section');
            const newTermsBody = document.getElementById('new-terms-body');
            
            if (data.new_terms && data.new_terms.length > 0) {
                newTermsSection.classList.remove('hidden');
                newTermsBody.innerHTML = data.new_terms.map((t, i) => `
                    <tr>
                        <td class="checkbox-cell">
                            <input type="checkbox" checked data-new-term="${i}">
                        </td>
                        <td>${t.vocabulary_code}</td>
                        <td>${t.term}</td>
                        <td>${t.code || '-'}</td>
                    </tr>
                `).join('');
            } else {
                newTermsSection.classList.add('hidden');
            }
            
            // Units
            const container = document.getElementById('units-container');
            container.innerHTML = data.units.map((unit, ui) => `
                <div class="unit-card">
                    <div class="unit-header">
                        <span class="unit-path">${unit.path_label}</span>
                        <span class="unit-type">${unit.unit_type}</span>
                    </div>
                    <div class="unit-content">${unit.content}</div>
                    
                    ${unit.existing_tags.length > 0 ? `
                    <div class="tags-section">
                        <div class="tags-title">
                            <span class="icon">📌</span>
                            برچسب‌های موجود (${unit.existing_tags.length})
                        </div>
                        <table class="tag-table">
                            <thead>
                                <tr><th>موضوع</th><th>برچسب</th><th>وزن</th></tr>
                            </thead>
                            <tbody>
                                ${unit.existing_tags.map(t => `
                                    <tr class="tag-existing">
                                        <td>${t.vocabulary}</td>
                                        <td>${t.term}</td>
                                        <td><span class="weight-badge ${getWeightClass(t.weight)}">${t.weight}</span></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                    ` : ''}
                    
                    ${unit.suggested_tags.length > 0 ? `
                    <div class="tags-section">
                        <div class="tags-title">
                            <span class="icon">🤖</span>
                            برچسب‌های پیشنهادی (${unit.suggested_tags.length})
                        </div>
                        <table class="tag-table">
                            <thead>
                                <tr>
                                    <th class="checkbox-cell">✓</th>
                                    <th>موضوع</th>
                                    <th>برچسب</th>
                                    <th>وزن</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${unit.suggested_tags.map((t, ti) => `
                                    <tr class="${t.valid ? 'tag-new' : 'tag-invalid'}">
                                        <td class="checkbox-cell">
                                            <input type="checkbox" ${t.valid ? 'checked' : 'disabled'} 
                                                   data-unit="${ui}" data-tag="${ti}">
                                        </td>
                                        <td>${t.vocabulary}</td>
                                        <td>${t.term}</td>
                                        <td><span class="weight-badge ${getWeightClass(t.weight)}">${t.weight}</span></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                    ` : '<div class="tags-section"><em style="color:#888">بدون برچسب پیشنهادی</em></div>'}
                </div>
            `).join('');
        }
        
        function getWeightClass(w) {
            if (w >= 7) return 'weight-high';
            if (w >= 4) return 'weight-mid';
            return 'weight-low';
        }
        
        function collectApprovedData() {
            const result = {
                units: [],
                new_terms: []
            };
            
            // Collect new terms
            document.querySelectorAll('[data-new-term]').forEach(cb => {
                const idx = parseInt(cb.dataset.newTerm);
                if (cb.checked && currentData.new_terms[idx]) {
                    result.new_terms.push({
                        ...currentData.new_terms[idx],
                        approved: true
                    });
                }
            });
            
            // Collect unit tags
            currentData.units.forEach((unit, ui) => {
                const unitResult = {
                    unit_id: unit.unit_id,
                    tags: []
                };
                
                document.querySelectorAll(`[data-unit="${ui}"]`).forEach(cb => {
                    const ti = parseInt(cb.dataset.tag);
                    if (cb.checked && unit.suggested_tags[ti] && unit.suggested_tags[ti].valid) {
                        unitResult.tags.push({
                            term_id: unit.suggested_tags[ti].term_id,
                            weight: unit.suggested_tags[ti].weight,
                            approved: true
                        });
                    }
                });
                
                if (unitResult.tags.length > 0) {
                    result.units.push(unitResult);
                }
            });
            
            return result;
        }
        
        function approveAll() {
            // Check all checkboxes first
            document.querySelectorAll('[data-unit], [data-new-term]').forEach(cb => {
                if (!cb.disabled) cb.checked = true;
            });
            approveSelected();
        }
        
        function approveSelected() {
            const data = collectApprovedData();
            document.getElementById('results-section').classList.add('hidden');
            document.getElementById('loading-section').classList.remove('hidden');
            
            fetch('/api/approve', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            })
            .then(r => r.json())
            .then(() => {
                updateStatus();
                // Start next batch
                startProcess();
            });
        }
        
        function skipBatch() {
            document.getElementById('results-section').classList.add('hidden');
            fetch('/api/skip', {method: 'POST'})
                .then(() => {
                    updateStatus();
                });
        }
        
        // Initial load
        fetch('/api/init', {method: 'POST'}).then(() => updateStatus());
        setInterval(updateStatus, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/init', methods=['POST'])
def api_init():
    load_vocabularies_and_terms()
    state["total_units"] = count_untagged()
    state["total_batches"] = (state["total_units"] + BATCH_SIZE - 1) // BATCH_SIZE
    return jsonify({"success": True})

@app.route('/api/status')
def api_status():
    return jsonify({
        "status": state["status"],
        "current_batch": state["current_batch"],
        "total_batches": state["total_batches"],
        "total_units": state["total_units"],
        "processed_units": state["processed_units"],
        "logs": state["logs"][-30:]
    })

@app.route('/api/start', methods=['POST'])
def api_start():
    if state["status"] != "idle":
        return jsonify({"success": False, "error": "Already running"})
    
    thread = threading.Thread(target=process_next_batch)
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True})

@app.route('/api/results')
def api_results():
    if state["current_results"]:
        return jsonify(state["current_results"])
    return jsonify({"units": [], "new_terms": []})

@app.route('/api/approve', methods=['POST'])
def api_approve():
    data = request.json
    saved_tags, saved_terms = save_approved_batch(data)
    state["current_results"] = None
    # Refresh term list if new terms were added
    if saved_terms > 0:
        load_vocabularies_and_terms()
    return jsonify({"success": True, "saved_tags": saved_tags, "saved_terms": saved_terms})

@app.route('/api/skip', methods=['POST'])
def api_skip():
    state["status"] = "idle"
    state["current_results"] = None
    log("Batch skipped by user")
    return jsonify({"success": True})

if __name__ == '__main__':
    print("=" * 60)
    print("Legal Unit Intelligent Tagger v2")
    print("=" * 60)
    print(f"Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    print(f"Model: {MODEL_NAME}")
    print(f"Batch Size: {BATCH_SIZE}")
    print("=" * 60)
    print("Open http://localhost:5000 in your browser")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
