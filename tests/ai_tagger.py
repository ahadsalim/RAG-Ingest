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
BATCH_SIZE = 5  # Smaller batch for better accuracy and faster API response

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
    "prefetch_results": None,  # Pre-fetched next batch results
    "prefetch_status": "idle",  # idle, fetching, ready
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

# فقط این نوع واحدها نیاز به برچسب دارند (مقادیر انگلیسی در دیتابیس)
VALID_UNIT_TYPES = ['full_text', 'article', 'clause', 'subclause', 'note']

def get_units(limit=30, offset=0):
    """Get ALL legal units (not just untagged) - only specific unit types."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # فیلتر بر اساس نوع واحد
    type_placeholders = ','.join(['%s'] * len(VALID_UNIT_TYPES))
    
    cur.execute(f"""
        SELECT lu.id, lu.path_label, lu.content, lu.unit_type, w.title_official as document_title, lu.work_id
        FROM documents_legalunit lu
        LEFT JOIN documents_instrumentwork w ON lu.work_id = w.id
        WHERE lu.content IS NOT NULL AND lu.content != ''
          AND lu.unit_type IN ({type_placeholders})
        ORDER BY lu.work_id, lu.lft
        LIMIT %s OFFSET %s
    """, (*VALID_UNIT_TYPES, limit, offset))
    
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

def count_total_units():
    """Count ALL units (not just untagged)."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    type_placeholders = ','.join(['%s'] * len(VALID_UNIT_TYPES))
    
    cur.execute(f"""
        SELECT COUNT(*) as count FROM documents_legalunit lu
        WHERE lu.content IS NOT NULL AND lu.content != ''
          AND lu.unit_type IN ({type_placeholders})
    """, VALID_UNIT_TYPES)
    result = cur.fetchone()
    conn.close()
    return result["count"]

def build_prompt(units):
    """Build prompt for GPT based on Legal Tagging Engine template."""
    
    system = """تو یک Legal Tagging Engine هستی. برای هر بند قانون، برچسب‌های مرتبط را از لیست existing_tags انتخاب کن.

## دستورالعمل:
1. برای هر unit_id، از لیست existing_tags برچسب‌های مرتبط را انتخاب کن
2. به هر برچسب وزن 1-10 بده (10=خیلی مرتبط، 1=کم‌ربط)
3. حداکثر 10 برچسب برای هر بند
4. اگر مفهوم مهمی در existing_tags نیست، در new_tags پیشنهاد بده

## راهنمای وزن:
- هسته اصلی بند: 9-10
- موضوع فرعی مهم: 6-8
- مرتبط ولی غیرمستقیم: 3-5

## خروجی JSON (بدون هیچ متن اضافه):
{
  "results": [
    {
      "unit_id": "uuid",
      "final_tags": [{"term_id": "uuid-from-existing", "tag": "نام", "weight": 8}],
      "new_tags": [{"tag": "برچسب جدید", "weight": 7, "vocabulary_code": "code"}]
    }
  ]
}

مهم: term_id باید دقیقاً از ستون term_id جدول existing_tags کپی شود."""

    # Build existing tags as simple list grouped by vocabulary
    tags_by_vocab = {}
    for t in state["terms"]:
        vname = t['vocabulary_name']
        if vname not in tags_by_vocab:
            tags_by_vocab[vname] = []
        tags_by_vocab[vname].append({"id": str(t['id']), "term": t['term']})
    
    tags_list = "## existing_tags:\n\n"
    for vname, terms in tags_by_vocab.items():
        tags_list += f"### {vname}:\n"
        for t in terms:
            tags_list += f"- term_id: `{t['id']}` → {t['term']}\n"
        tags_list += "\n"
    
    # Build units/clauses - more compact format
    clauses = "\n## بندها برای برچسب‌گذاری:\n\n"
    for u in units:
        content = u['content']
        if len(content) > 800:
            content = content[:800] + "..."
        doc_title = u.get('document_title', '-') or '-'
        clauses += f"### unit_id: `{u['id']}`\n"
        clauses += f"قانون: {doc_title}\n"
        clauses += f"مسیر: {u['path_label']} | نوع: {u['unit_type']}\n"
        clauses += f"متن:\n{content}\n\n---\n\n"
    
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
    log(f"Calling GPT API ({MODEL_NAME})...")
    log(f"Prompt size: system={len(system)} chars, user={len(user)} chars")
    
    try:
        client = OpenAI(
            api_key=OPENAI_API_KEY, 
            base_url=OPENAI_BASE_URL,
            timeout=180.0  # 3 minute timeout
        )
        
        log("Sending request to API...")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=0.3
        )
        
        result = response.choices[0].message.content
        log(f"Got response: {len(result)} chars")
        
        # Extract JSON from response (may have extra text)
        if result.strip().startswith('{'):
            return result
        
        # Try to find JSON in response
        import re
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            return json_match.group()
        
        log(f"Warning: No JSON found in response")
        return '{"results": []}'
        
    except Exception as e:
        log(f"API Error: {type(e).__name__}: {e}")
        raise

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
    
    # Calculate offset for pagination
    offset = (state["current_batch"] - 1) * BATCH_SIZE
    
    log(f"Batch {state['current_batch']}: Loading units (offset={offset})...")
    units = get_units(BATCH_SIZE, offset)
    
    if not units:
        log("No more units to process!")
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
                'document_title': unit.get('document_title', '-'),
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
        
        # Start prefetching next batch in background
        log("Starting prefetch thread...")
        try:
            prefetch_thread = threading.Thread(target=prefetch_next_batch)
            prefetch_thread.daemon = True
            prefetch_thread.start()
            log("Prefetch thread started successfully")
        except Exception as e:
            log(f"Failed to start prefetch thread: {e}")
        
        return True
        
    except Exception as e:
        log(f"Error: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        state["status"] = "idle"
        return False

def prefetch_next_batch():
    """Pre-fetch the next batch while user reviews current batch."""
    log(f"prefetch_next_batch called, current status: {state['prefetch_status']}")
    
    if state["prefetch_status"] == "fetching":
        log("Prefetch already in progress, skipping")
        return
    
    next_batch = state["current_batch"] + 1
    log(f"Next batch would be: {next_batch}, total batches: {state['total_batches']}")
    
    if next_batch > state["total_batches"]:
        log("No more batches to prefetch")
        return
    
    state["prefetch_status"] = "fetching"
    log(f"🔄 Pre-fetching batch {next_batch}...")
    
    try:
        offset = (next_batch - 1) * BATCH_SIZE
        units = get_units(BATCH_SIZE, offset)
        
        if not units:
            state["prefetch_status"] = "idle"
            return
        
        unit_map = {str(u['id']): u for u in units}
        unit_ids = list(unit_map.keys())
        existing_tags = get_existing_tags(unit_ids)
        
        system_prompt, user_prompt = build_prompt(units)
        
        # Save prompts
        save_prompt_to_file(system_prompt, user_prompt, f"prefetch_{next_batch}")
        
        response = call_gpt(system_prompt, user_prompt)
        
        # Save response
        with open(f"response_prefetch_{next_batch}.json", "w", encoding="utf-8") as f:
            f.write(response)
        
        results = json.loads(response)
        
        # Process results same as process_next_batch
        display_data = []
        all_new_terms = []
        
        for unit_result in results.get('results', []):
            uid = unit_result.get('unit_id', '')
            if uid not in unit_map:
                continue
            
            unit = unit_map[uid]
            suggested_tags = []
            
            for tag in unit_result.get('tags', []):
                term_id = tag.get('term_id', '')
                is_valid = term_id in state["valid_term_ids"]
                term_info = state["term_lookup"].get(term_id, {})
                
                suggested_tags.append({
                    'term_id': term_id,
                    'term': term_info.get('term', tag.get('term', '?')),
                    'vocabulary': term_info.get('vocabulary_name', '?'),
                    'weight': tag.get('weight', 5),
                    'valid': is_valid
                })
            
            for new_tag in unit_result.get('new_tags', []):
                all_new_terms.append({
                    'unit_id': uid,
                    'vocabulary_code': new_tag.get('vocabulary_code'),
                    'tag': new_tag.get('tag'),
                    'weight': new_tag.get('weight', 5)
                })
                suggested_tags.append({
                    'term_id': None,
                    'term': f"🆕 {new_tag.get('tag')}",
                    'vocabulary': new_tag.get('vocabulary_code', 'جدید'),
                    'weight': new_tag.get('weight', 5),
                    'valid': True,
                    'is_new': True,
                    'new_tag_data': new_tag
                })
            
            display_data.append({
                'unit_id': uid,
                'document_title': unit.get('document_title', '-'),
                'path_label': unit['path_label'],
                'unit_type': unit['unit_type'],
                'content': unit['content'],
                'existing_tags': existing_tags.get(uid, []),
                'suggested_tags': suggested_tags
            })
        
        state["prefetch_results"] = {
            'units': display_data,
            'new_terms': all_new_terms,
            'raw_results': results,
            'batch_number': next_batch
        }
        state["prefetch_status"] = "ready"
        log(f"Pre-fetch batch {next_batch} ready!")
        
    except Exception as e:
        import traceback
        log(f"❌ Pre-fetch error: {e}")
        log(f"Traceback: {traceback.format_exc()}")
        state["prefetch_status"] = "idle"
        state["prefetch_results"] = None

def save_approved_batch(approved_data):
    """Save approved tags to database."""
    state["status"] = "saving"
    conn = get_db_connection()
    cur = conn.cursor()
    
    saved_tags = 0
    saved_terms = 0
    
    # Save new terms from AI first
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
    
    # Save manual new terms and link to units
    manual_term_map = {}  # tag_name -> term_id
    for term in approved_data.get('manual_new_terms', []):
        try:
            vocab_id = term.get('vocabulary_id', '')
            tag_name = term.get('tag', '')
            unit_id = term.get('unit_id', '')
            weight = term.get('weight', 7)
            
            if not vocab_id or not tag_name:
                continue
            
            # Check if we already created this term
            if tag_name in manual_term_map:
                term_id = manual_term_map[tag_name]
            else:
                term_id = str(uuid.uuid4())
                tag_code = ''.join(word.capitalize() for word in tag_name.split())
                cur.execute("""
                    INSERT INTO masterdata_vocabularyterm (id, vocabulary_id, term, code, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, true, NOW(), NOW())
                    ON CONFLICT DO NOTHING
                """, (term_id, vocab_id, tag_name, tag_code))
                conn.commit()
                saved_terms += 1
                state["valid_term_ids"].add(term_id)
                manual_term_map[tag_name] = term_id
                log(f"Added manual term: {tag_name}")
            
            # Link to unit
            if unit_id:
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
            log(f"Error saving manual term: {e}")
    
    # Save AI tags
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
        
        # Save manual existing tags
        for tag in unit.get('manual_tags', []):
            term_id = tag['term_id']
            weight = tag.get('weight', 7)
            
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
                log(f"Error saving manual tag: {e}")
    
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
        /* Base: 12px, Range: 11px-13px */
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Vazirmatn', Tahoma, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 15px;
            min-height: 100vh;
            font-size: 12px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { text-align: center; color: #00d4ff; margin-bottom: 15px; font-size: 13px; font-weight: bold; }
        
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
        .stat-value { font-size: 13px; font-weight: bold; color: #00d4ff; }
        .stat-label { color: #aaa; font-size: 11px; }
        
        .controls { text-align: center; margin: 15px 0; }
        .btn {
            padding: 8px 20px;
            font-size: 12px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            margin: 3px;
            transition: all 0.3s;
        }
        .btn-primary { background: linear-gradient(90deg, #00d4ff, #00ff88); color: #000; }
        .btn-success { background: #00ff88; color: #000; }
        .btn-danger { background: #ff4444; color: #fff; }
        .btn:hover { transform: scale(1.03); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        
        .status {
            text-align: center;
            padding: 8px;
            border-radius: 6px;
            margin: 8px 0;
            font-size: 12px;
        }
        .status-idle { background: rgba(100,100,100,0.3); }
        .status-processing { background: rgba(0,212,255,0.3); }
        .status-waiting { background: rgba(255,200,0,0.3); }
        .status-prefetching { background: rgba(138,43,226,0.3); }
        
        .log-box {
            background: #0a0a15;
            border-radius: 6px;
            padding: 10px;
            max-height: 100px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 11px;
            margin-bottom: 15px;
        }
        
        .unit-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .unit-header {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            gap: 8px;
        }
        .unit-doc { color: #ffcc00; font-size: 12px; width: 100%; }
        .unit-path { color: #00d4ff; font-weight: bold; font-size: 12px; }
        .unit-type { 
            background: rgba(0,212,255,0.2);
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
        }
        .unit-content {
            background: rgba(0,0,0,0.3);
            padding: 10px;
            border-radius: 6px;
            margin-bottom: 10px;
            line-height: 1.6;
            max-height: 120px;
            overflow-y: auto;
            font-size: 12px;
        }
        
        .tags-section { margin-top: 10px; }
        .tags-title { 
            font-weight: bold; 
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
        }
        .tags-title .icon { font-size: 12px; }
        
        .tag-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
        }
        .tag-table th, .tag-table td {
            padding: 5px 8px;
            text-align: right;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .tag-table th {
            background: rgba(0,212,255,0.1);
            color: #00d4ff;
            font-size: 11px;
        }
        .tag-table tr:hover { background: rgba(255,255,255,0.05); }
        
        .tag-existing { color: #ffcc00; }
        .tag-new { color: #00ff88; }
        .tag-invalid { color: #ff4444; text-decoration: line-through; }
        
        .weight-badge {
            display: inline-block;
            width: 22px;
            height: 22px;
            line-height: 22px;
            text-align: center;
            border-radius: 50%;
            font-weight: bold;
            font-size: 11px;
        }
        .weight-high { background: #00ff88; color: #000; }
        .weight-mid { background: #ffcc00; color: #000; }
        .weight-low { background: #ff8844; color: #000; }
        
        .checkbox-cell { width: 30px; text-align: center; }
        .checkbox-cell input { width: 14px; height: 14px; cursor: pointer; }
        
        .new-terms-section {
            background: rgba(0,255,136,0.1);
            border: 1px solid rgba(0,255,136,0.3);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .new-terms-title { color: #00ff88; margin-bottom: 10px; font-size: 12px; }
        
        .manual-tag-section {
            margin-top: 10px;
            padding: 10px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
        }
        .manual-tag-title {
            font-size: 12px;
            color: #aaa;
            margin-bottom: 8px;
        }
        .tag-search-container {
            position: relative;
        }
        .tag-search-input {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 6px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 12px;
        }
        .tag-search-input:focus {
            outline: none;
            border-color: #00d4ff;
        }
        .tag-suggestions {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: #1a1a2e;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 6px;
            max-height: 200px;
            overflow-y: auto;
            z-index: 100;
            display: none;
        }
        .tag-suggestions.show { display: block; }
        .tag-suggestion-item {
            padding: 8px 12px;
            cursor: pointer;
            font-size: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .tag-suggestion-item:hover { background: rgba(0,212,255,0.2); }
        .tag-suggestion-item .vocab-name { color: #888; font-size: 11px; }
        .tag-suggestion-new {
            background: rgba(0,255,136,0.1);
            color: #00ff88;
        }
        .manual-tags-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
            padding: 10px;
            background: rgba(138,43,226,0.1);
            border-radius: 8px;
            min-height: 40px;
        }
        .manual-tags-list:empty::before {
            content: '🏷️ برچسب‌های دستی شما اینجا نمایش داده می‌شود...';
            color: #888;
            font-size: 11px;
            font-style: italic;
        }
        .manual-tag-chip {
            background: linear-gradient(135deg, rgba(138,43,226,0.5), rgba(0,212,255,0.3));
            border: 2px solid rgba(138,43,226,0.8);
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            animation: tagAdded 0.5s ease-out;
            box-shadow: 0 2px 8px rgba(138,43,226,0.3);
        }
        .manual-tag-chip:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(138,43,226,0.5);
        }
        @keyframes tagAdded {
            0% { transform: scale(0); opacity: 0; }
            50% { transform: scale(1.2); }
            100% { transform: scale(1); opacity: 1; }
        }
        .manual-tag-chip .tag-name {
            font-weight: bold;
            color: #fff;
        }
        .manual-tag-chip .tag-vocab {
            color: #aaa;
            font-size: 11px;
        }
        .manual-tag-chip .tag-weight {
            background: #00ff88;
            color: #000;
            padding: 2px 6px;
            border-radius: 10px;
            font-weight: bold;
            font-size: 10px;
        }
        .manual-tag-chip .remove-tag {
            cursor: pointer;
            color: #ff4444;
            font-size: 14px;
            margin-right: 4px;
        }
        .manual-tag-chip .remove-tag:hover {
            color: #ff0000;
            transform: scale(1.2);
        }
        .vocab-select-modal {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        .vocab-select-content {
            background: #1a1a2e;
            padding: 20px;
            border-radius: 12px;
            min-width: 300px;
            max-width: 400px;
        }
        .vocab-select-title { color: #00d4ff; margin-bottom: 15px; font-size: 13px; }
        .vocab-select-list {
            max-height: 300px;
            overflow-y: auto;
        }
        .vocab-select-item {
            padding: 10px;
            cursor: pointer;
            border-radius: 6px;
            margin-bottom: 5px;
            font-size: 12px;
        }
        .vocab-select-item:hover { background: rgba(0,212,255,0.2); }
        .vocab-select-cancel {
            margin-top: 15px;
            text-align: center;
        }
        
        /* Add Tag Modal Styles */
        .add-tag-modal {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.85);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        .add-tag-content {
            background: #1a1a2e;
            padding: 25px;
            border-radius: 12px;
            min-width: 450px;
            max-width: 550px;
            max-height: 80vh;
            overflow-y: auto;
        }
        .add-tag-title {
            color: #00d4ff;
            font-size: 13px;
            font-weight: bold;
            margin-bottom: 20px;
            text-align: center;
        }
        .add-tag-section {
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
        }
        .add-tag-section-title {
            color: #ffcc00;
            font-size: 12px;
            margin-bottom: 10px;
        }
        .add-tag-input {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 6px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 12px;
            margin-bottom: 10px;
        }
        .add-tag-input:focus {
            outline: none;
            border-color: #00d4ff;
        }
        .add-tag-select {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 6px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 12px;
        }
        .add-tag-btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            margin: 5px;
        }
        .add-tag-btn-save {
            background: #00ff88;
            color: #000;
        }
        .add-tag-btn-cancel {
            background: #ff4444;
            color: #fff;
        }
        .add-tag-btn-create {
            background: #00d4ff;
            color: #000;
        }
        .add-tag-actions {
            text-align: center;
            margin-top: 20px;
        }
        .vocab-list-item {
            padding: 8px 12px;
            cursor: pointer;
            border-radius: 6px;
            margin-bottom: 5px;
            background: rgba(255,255,255,0.05);
            font-size: 12px;
        }
        .vocab-list-item:hover {
            background: rgba(0,212,255,0.2);
        }
        .vocab-list-item.selected {
            background: rgba(0,212,255,0.3);
            border: 1px solid #00d4ff;
        }
        .new-vocab-form {
            display: none;
            margin-top: 10px;
            padding: 10px;
            background: rgba(0,255,136,0.1);
            border-radius: 6px;
        }
        .new-vocab-form.show {
            display: block;
        }
        .weight-input {
            width: 60px;
            padding: 5px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 4px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 12px;
        }
        
        .prefetch-indicator {
            position: fixed;
            bottom: 10px;
            left: 10px;
            background: rgba(138,43,226,0.8);
            color: #fff;
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 11px;
            z-index: 999;
        }
        
        .hidden { display: none; }
        
        .loading {
            text-align: center;
            padding: 40px;
            font-size: 13px;
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
                <div class="stat-label">کل بندها</div>
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
                        <div class="unit-doc">📄 ${unit.document_title || '-'}</div>
                        <span class="unit-path">${unit.path_label}</span>
                        <span class="unit-type">${unit.unit_type}</span>
                    </div>
                    <div class="unit-content">${unit.content}</div>
                    
                    <div class="tags-section">
                        <div class="tags-title">
                            <span class="icon">📌</span>
                            برچسب‌های قبلی (${unit.existing_tags.length})
                        </div>
                        ${unit.existing_tags.length > 0 ? `
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
                        ` : '<em style="color:#888;font-size:0.85em">بدون برچسب قبلی</em>'}
                    </div>
                    
                    <div class="tags-section">
                        <div class="tags-title">
                            <span class="icon">🤖</span>
                            برچسب‌های پیشنهادی جدید (${unit.suggested_tags.length})
                        </div>
                        ${unit.suggested_tags.length > 0 ? `
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
                        ` : '<em style="color:#888;font-size:0.85em">بدون برچسب پیشنهادی</em>'}
                    </div>
                    
                    <!-- Manual Tag Input -->
                    <div class="manual-tag-section">
                        <div class="manual-tag-title">
                            ✏️ افزودن برچسب دستی:
                            <button class="add-tag-btn add-tag-btn-create" style="margin-right:10px;padding:4px 10px;font-size:0.8em;" 
                                    data-unit-idx="${ui}" onclick="openAddTagModal(${ui})">
                                ➕ افزودن برچسب جدید
                            </button>
                        </div>
                        <div class="tag-search-container">
                            <input type="text" class="tag-search-input" 
                                   placeholder="جستجوی برچسب موجود..."
                                   data-unit-idx="${ui}"
                                   oninput="searchTags(this, ${ui})"
                                   onkeydown="handleTagKeydown(event, ${ui})">
                            <div class="tag-suggestions" id="suggestions-${ui}"></div>
                        </div>
                        <div class="manual-tags-list" id="manual-tags-${ui}"></div>
                    </div>
                </div>
            `).join('');
        }
        
        // Store manual tags per unit
        let manualTags = {};
        let allTerms = [];
        let allVocabs = [];
        
        function loadTermsAndVocabs() {
            fetch('/api/terms').then(r => r.json()).then(data => {
                allTerms = data.terms || [];
                allVocabs = data.vocabularies || [];
            });
        }
        
        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }
        
        function searchTags(input, unitIdx) {
            const query = input.value.trim().toLowerCase();
            const suggestionsDiv = document.getElementById('suggestions-' + unitIdx);
            
            if (query.length < 1) {
                suggestionsDiv.classList.remove('show');
                return;
            }
            
            // Filter matching terms
            const matches = allTerms.filter(t => 
                t.term && t.term.toLowerCase().includes(query)
            ).slice(0, 10);
            
            let html = matches.map((t, idx) => {
                // Store all term info in data attributes
                return `
                    <div class="tag-suggestion-item" 
                         data-term-id="${t.id}" 
                         data-term-name="${escapeHtml(t.term)}" 
                         data-vocab-name="${escapeHtml(t.vocabulary_name || '')}"
                         data-unit-idx="${unitIdx}">
                        <div>${escapeHtml(t.term)}</div>
                        <div class="vocab-name">${escapeHtml(t.vocabulary_name || '')}</div>
                    </div>
                `;
            }).join('');
            
            // Add "create new" option if no exact match
            const exactMatch = allTerms.find(t => t.term && t.term.toLowerCase() === query);
            if (!exactMatch && query.length > 1) {
                const safeInput = escapeHtml(input.value.trim());
                html += `
                    <div class="tag-suggestion-item tag-suggestion-new" data-new-tag="${safeInput}" data-unit-idx="${unitIdx}">
                        <div>🆕 ایجاد برچسب جدید: "${safeInput}"</div>
                    </div>
                `;
            }
            
            suggestionsDiv.innerHTML = html;
            suggestionsDiv.classList.add('show');
            
            // Add click handlers - use data attributes directly
            suggestionsDiv.querySelectorAll('.tag-suggestion-item').forEach(item => {
                item.onclick = function(e) {
                    e.stopPropagation();
                    const newTag = this.dataset.newTag;
                    const unitIdx = parseInt(this.dataset.unitIdx);
                    
                    console.log('Item clicked:', this.dataset);
                    
                    if (newTag) {
                        createNewTag(unitIdx, newTag);
                    } else {
                        const termId = this.dataset.termId;
                        const termName = this.dataset.termName;
                        const vocabName = this.dataset.vocabName;
                        console.log('Selecting existing tag:', termId, termName, vocabName);
                        selectExistingTag(unitIdx, termId, termName, vocabName);
                    }
                };
            });
        }
        
        function handleTagKeydown(event, unitIdx) {
            if (event.key === 'Escape') {
                document.getElementById('suggestions-' + unitIdx).classList.remove('show');
            }
        }
        
        function selectExistingTag(unitIdx, termId, termName, vocabName) {
            console.log('selectExistingTag called:', unitIdx, termId, termName, vocabName);
            
            if (!manualTags[unitIdx]) manualTags[unitIdx] = [];
            
            // Check if already added
            if (manualTags[unitIdx].find(t => t.term_id === termId)) {
                alert('این برچسب قبلاً اضافه شده است');
                return;
            }
            
            // Ask for weight
            const weight = prompt('وزن برچسب را وارد کنید (1-10):', '7');
            if (weight === null) return; // User cancelled
            const weightNum = parseInt(weight) || 7;
            
            manualTags[unitIdx].push({
                term_id: termId,
                term: termName,
                vocabulary: vocabName,
                weight: Math.min(10, Math.max(1, weightNum)),
                is_new: false
            });
            
            console.log('manualTags after push:', JSON.stringify(manualTags));
            
            renderManualTags(unitIdx);
            
            // Clear input
            const input = document.querySelector(`[data-unit-idx="${unitIdx}"]`);
            if (input) input.value = '';
            const suggestions = document.getElementById('suggestions-' + unitIdx);
            if (suggestions) suggestions.classList.remove('show');
        }
        
        function createNewTag(unitIdx, tagName) {
            // Show vocabulary selection modal
            showVocabModal(unitIdx, tagName);
        }
        
        function showVocabModal(unitIdx, tagName) {
            const modal = document.createElement('div');
            modal.className = 'vocab-select-modal';
            modal.id = 'vocab-modal';
            
            const safeTagName = escapeHtml(tagName);
            let vocabListHtml = allVocabs.map((v, idx) => `
                <div class="vocab-select-item" data-vocab-idx="${idx}">
                    ${escapeHtml(v.name)}
                </div>
            `).join('');
            
            modal.innerHTML = `
                <div class="vocab-select-content">
                    <div class="vocab-select-title">انتخاب موضوع برای برچسب: "${safeTagName}"</div>
                    <div class="vocab-select-list">
                        ${vocabListHtml}
                    </div>
                    <div class="vocab-select-cancel">
                        <button class="btn btn-danger" id="cancel-vocab-btn">انصراف</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            
            // Add click handlers
            modal.querySelectorAll('.vocab-select-item').forEach(item => {
                item.onclick = function() {
                    const vocabIdx = parseInt(this.dataset.vocabIdx);
                    const vocab = allVocabs[vocabIdx];
                    if (vocab) {
                        confirmNewTag(unitIdx, tagName, vocab.id, vocab.name);
                    }
                };
            });
            
            document.getElementById('cancel-vocab-btn').onclick = closeVocabModal;
        }
        
        function closeVocabModal() {
            const modal = document.getElementById('vocab-modal');
            if (modal) modal.remove();
        }
        
        function confirmNewTag(unitIdx, tagName, vocabId, vocabName) {
            if (!manualTags[unitIdx]) manualTags[unitIdx] = [];
            
            manualTags[unitIdx].push({
                term_id: null,
                term: tagName,
                vocabulary: vocabName,
                vocabulary_id: vocabId,
                weight: 7,
                is_new: true
            });
            
            renderManualTags(unitIdx);
            closeVocabModal();
            
            // Clear input
            const input = document.querySelector(`[data-unit-idx="${unitIdx}"]`);
            input.value = '';
            document.getElementById('suggestions-' + unitIdx).classList.remove('show');
        }
        
        function renderManualTags(unitIdx) {
            console.log('renderManualTags called for unit:', unitIdx);
            const container = document.getElementById('manual-tags-' + unitIdx);
            
            if (!container) {
                console.error('Container not found for unit:', unitIdx);
                return;
            }
            
            const tags = manualTags[unitIdx] || [];
            console.log('tags to render:', tags.length);
            
            if (tags.length === 0) {
                container.innerHTML = '';
                return;
            }
            
            container.innerHTML = tags.map((t, i) => `
                <div class="manual-tag-chip">
                    <span class="tag-name">${t.is_new ? '🆕 ' : ''}${escapeHtml(t.term)}</span>
                    <span class="tag-vocab">${escapeHtml(t.vocabulary)}</span>
                    <span class="tag-weight">${t.weight}</span>
                    <span class="remove-tag" data-unit="${unitIdx}" data-tag-idx="${i}">✕</span>
                </div>
            `).join('');
            
            // Add click handlers for remove buttons
            container.querySelectorAll('.remove-tag').forEach(btn => {
                btn.onclick = function() {
                    const unitIdx = parseInt(this.dataset.unit);
                    const tagIdx = parseInt(this.dataset.tagIdx);
                    removeManualTag(unitIdx, tagIdx);
                };
            });
        }
        
        function removeManualTag(unitIdx, tagIdx) {
            if (manualTags[unitIdx]) {
                manualTags[unitIdx].splice(tagIdx, 1);
                renderManualTags(unitIdx);
            }
        }
        
        // ============================================
        // Add Tag Modal Functions
        // ============================================
        let currentAddTagUnitIdx = null;
        let selectedVocabId = null;
        let selectedVocabName = null;
        
        function openAddTagModal(unitIdx) {
            currentAddTagUnitIdx = unitIdx;
            selectedVocabId = null;
            selectedVocabName = null;
            
            const modal = document.createElement('div');
            modal.className = 'add-tag-modal';
            modal.id = 'add-tag-modal';
            
            let vocabListHtml = allVocabs.map((v, idx) => `
                <div class="vocab-list-item" data-vocab-idx="${idx}" data-vocab-id="${v.id}">
                    ${escapeHtml(v.name)}
                </div>
            `).join('');
            
            modal.innerHTML = `
                <div class="add-tag-content">
                    <div class="add-tag-title">➕ افزودن برچسب جدید</div>
                    
                    <!-- Vocabulary Section -->
                    <div class="add-tag-section">
                        <div class="add-tag-section-title">📁 انتخاب یا ایجاد موضوع (Vocabulary):</div>
                        <div style="max-height:150px;overflow-y:auto;margin-bottom:10px;" id="vocab-list">
                            ${vocabListHtml}
                        </div>
                        <button class="add-tag-btn add-tag-btn-create" id="show-new-vocab-btn">
                            🆕 ایجاد موضوع جدید
                        </button>
                        <div class="new-vocab-form" id="new-vocab-form">
                            <input type="text" class="add-tag-input" id="new-vocab-name" placeholder="نام موضوع جدید...">
                            <input type="text" class="add-tag-input" id="new-vocab-code" placeholder="کد موضوع (انگلیسی)...">
                            <button class="add-tag-btn add-tag-btn-save" id="save-new-vocab-btn">💾 ذخیره موضوع</button>
                        </div>
                        <div id="selected-vocab-display" style="margin-top:10px;color:#00ff88;display:none;">
                            ✅ موضوع انتخاب شده: <span id="selected-vocab-name"></span>
                        </div>
                    </div>
                    
                    <!-- Term Section -->
                    <div class="add-tag-section">
                        <div class="add-tag-section-title">🏷️ برچسب جدید (Vocabulary Term):</div>
                        <input type="text" class="add-tag-input" id="new-term-name" placeholder="نام برچسب...">
                        <input type="text" class="add-tag-input" id="new-term-code" placeholder="کد برچسب (انگلیسی، اختیاری)...">
                        <div style="display:flex;align-items:center;gap:10px;margin-top:10px;">
                            <label>وزن:</label>
                            <input type="number" class="weight-input" id="new-term-weight" value="7" min="1" max="10">
                        </div>
                    </div>
                    
                    <div class="add-tag-actions">
                        <button class="add-tag-btn add-tag-btn-save" id="save-term-btn">💾 ذخیره برچسب و افزودن به بند</button>
                        <button class="add-tag-btn add-tag-btn-cancel" id="cancel-add-tag-btn">❌ انصراف</button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // Add event listeners
            setupAddTagModalEvents();
        }
        
        function setupAddTagModalEvents() {
            // Vocab list item click
            document.querySelectorAll('#vocab-list .vocab-list-item').forEach(item => {
                item.onclick = function() {
                    document.querySelectorAll('#vocab-list .vocab-list-item').forEach(i => i.classList.remove('selected'));
                    this.classList.add('selected');
                    const vocabIdx = parseInt(this.dataset.vocabIdx);
                    const vocab = allVocabs[vocabIdx];
                    selectedVocabId = vocab.id;
                    selectedVocabName = vocab.name;
                    document.getElementById('selected-vocab-display').style.display = 'block';
                    document.getElementById('selected-vocab-name').textContent = vocab.name;
                    document.getElementById('new-vocab-form').classList.remove('show');
                };
            });
            
            // Show new vocab form
            document.getElementById('show-new-vocab-btn').onclick = function() {
                document.getElementById('new-vocab-form').classList.toggle('show');
            };
            
            // Save new vocab
            document.getElementById('save-new-vocab-btn').onclick = async function() {
                const name = document.getElementById('new-vocab-name').value.trim();
                const code = document.getElementById('new-vocab-code').value.trim();
                
                if (!name || !code) {
                    alert('لطفاً نام و کد موضوع را وارد کنید');
                    return;
                }
                
                try {
                    const response = await fetch('/api/create_vocabulary', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({name, code})
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        // Add to local list
                        allVocabs.push({id: data.id, name: name, code: code});
                        selectedVocabId = data.id;
                        selectedVocabName = name;
                        document.getElementById('selected-vocab-display').style.display = 'block';
                        document.getElementById('selected-vocab-name').textContent = name;
                        document.getElementById('new-vocab-form').classList.remove('show');
                        document.getElementById('new-vocab-name').value = '';
                        document.getElementById('new-vocab-code').value = '';
                        alert('موضوع با موفقیت ذخیره شد');
                    } else {
                        alert('خطا: ' + (data.error || 'نامشخص'));
                    }
                } catch (e) {
                    alert('خطا در ذخیره موضوع: ' + e.message);
                }
            };
            
            // Save term and add to unit
            document.getElementById('save-term-btn').onclick = async function() {
                const termName = document.getElementById('new-term-name').value.trim();
                const termCode = document.getElementById('new-term-code').value.trim();
                const weight = parseInt(document.getElementById('new-term-weight').value) || 7;
                
                if (!selectedVocabId) {
                    alert('لطفاً ابتدا یک موضوع انتخاب کنید');
                    return;
                }
                
                if (!termName) {
                    alert('لطفاً نام برچسب را وارد کنید');
                    return;
                }
                
                try {
                    const response = await fetch('/api/create_term', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            vocabulary_id: selectedVocabId,
                            term: termName,
                            code: termCode || termName.replace(/\s+/g, '')
                        })
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        // Add to local terms list
                        allTerms.push({
                            id: data.id,
                            term: termName,
                            vocabulary_id: selectedVocabId,
                            vocabulary_name: selectedVocabName
                        });
                        
                        // Add to manual tags for this unit
                        if (!manualTags[currentAddTagUnitIdx]) manualTags[currentAddTagUnitIdx] = [];
                        manualTags[currentAddTagUnitIdx].push({
                            term_id: data.id,
                            term: termName,
                            vocabulary: selectedVocabName,
                            weight: weight,
                            is_new: false  // Already saved to DB
                        });
                        
                        renderManualTags(currentAddTagUnitIdx);
                        closeAddTagModal();
                        alert('برچسب با موفقیت ذخیره و به بند اضافه شد');
                    } else {
                        alert('خطا: ' + (data.error || 'نامشخص'));
                    }
                } catch (e) {
                    alert('خطا در ذخیره برچسب: ' + e.message);
                }
            };
            
            // Cancel
            document.getElementById('cancel-add-tag-btn').onclick = closeAddTagModal;
        }
        
        function closeAddTagModal() {
            const modal = document.getElementById('add-tag-modal');
            if (modal) modal.remove();
            currentAddTagUnitIdx = null;
            selectedVocabId = null;
            selectedVocabName = null;
        }
        
        // Close suggestions when clicking outside
        document.addEventListener('click', function(e) {
            if (!e.target.classList.contains('tag-search-input')) {
                document.querySelectorAll('.tag-suggestions').forEach(el => el.classList.remove('show'));
            }
        });
        
        function getWeightClass(w) {
            if (w >= 7) return 'weight-high';
            if (w >= 4) return 'weight-mid';
            return 'weight-low';
        }
        
        function collectApprovedData() {
            const result = {
                units: [],
                new_terms: [],
                manual_new_terms: []
            };
            
            // Collect new terms from AI
            document.querySelectorAll('[data-new-term]').forEach(cb => {
                const idx = parseInt(cb.dataset.newTerm);
                if (cb.checked && currentData.new_terms[idx]) {
                    result.new_terms.push({
                        ...currentData.new_terms[idx],
                        approved: true
                    });
                }
            });
            
            // Collect unit tags (AI + manual)
            currentData.units.forEach((unit, ui) => {
                const unitResult = {
                    unit_id: unit.unit_id,
                    tags: [],
                    manual_tags: []
                };
                
                // AI suggested tags
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
                
                // Manual tags
                if (manualTags[ui]) {
                    manualTags[ui].forEach(mt => {
                        if (mt.is_new) {
                            // New term - add to manual_new_terms and manual_tags
                            result.manual_new_terms.push({
                                tag: mt.term,
                                vocabulary_id: mt.vocabulary_id,
                                vocabulary: mt.vocabulary,
                                unit_id: unit.unit_id,
                                weight: mt.weight
                            });
                        } else {
                            // Existing term
                            unitResult.manual_tags.push({
                                term_id: mt.term_id,
                                weight: mt.weight
                            });
                        }
                    });
                }
                
                if (unitResult.tags.length > 0 || unitResult.manual_tags.length > 0) {
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
            
            // Reset manual tags for next batch
            manualTags = {};
            
            fetch('/api/approve', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            })
            .then(r => r.json())
            .then(response => {
                updateStatus();
                
                // Check if prefetch is ready
                if (response.has_prefetch) {
                    // Use prefetched results immediately
                    fetch('/api/use_prefetch', {method: 'POST'})
                        .then(r => r.json())
                        .then(data => {
                            if (data.success) {
                                document.getElementById('loading-section').classList.add('hidden');
                                loadResults();
                            } else {
                                startProcess();
                            }
                        });
                } else {
                    // Start next batch normally
                    startProcess();
                }
            });
        }
        
        function skipBatch() {
            document.getElementById('results-section').classList.add('hidden');
            manualTags = {};
            fetch('/api/skip', {method: 'POST'})
                .then(() => {
                    updateStatus();
                });
        }
        
        // Show prefetch indicator
        function updatePrefetchIndicator() {
            fetch('/api/prefetch_status')
                .then(r => r.json())
                .then(data => {
                    console.log('Prefetch status:', data);
                    let indicator = document.getElementById('prefetch-indicator');
                    if (!indicator) {
                        indicator = document.createElement('div');
                        indicator.id = 'prefetch-indicator';
                        indicator.className = 'prefetch-indicator';
                        document.body.appendChild(indicator);
                    }
                    
                    if (data.status === 'fetching') {
                        indicator.textContent = '⏳ در حال آماده‌سازی دسته بعدی...';
                        indicator.style.display = 'block';
                    } else if (data.status === 'ready') {
                        indicator.textContent = '✅ دسته بعدی آماده است';
                        indicator.style.display = 'block';
                    } else {
                        indicator.style.display = 'none';
                    }
                })
                .catch(err => console.error('Prefetch status error:', err));
        }
        
        // Initial load
        fetch('/api/init', {method: 'POST'}).then(() => {
            updateStatus();
            loadTermsAndVocabs();
        });
        setInterval(updateStatus, 5000);
        setInterval(updatePrefetchIndicator, 3000);
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
    state["total_units"] = count_total_units()
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

@app.route('/api/terms')
def api_terms():
    """Return all terms and vocabularies for autocomplete."""
    return jsonify({
        "terms": state.get("terms", []),
        "vocabularies": state.get("vocabularies", [])
    })

@app.route('/api/create_vocabulary', methods=['POST'])
def api_create_vocabulary():
    """Create a new vocabulary."""
    data = request.json
    name = data.get('name', '').strip()
    code = data.get('code', '').strip()
    
    if not name or not code:
        return jsonify({"success": False, "error": "نام و کد الزامی است"})
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if code already exists
        cur.execute("SELECT id FROM masterdata_vocabulary WHERE code = %s", (code,))
        if cur.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "این کد قبلاً وجود دارد"})
        
        vocab_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO masterdata_vocabulary (id, name, code, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
        """, (vocab_id, name, code))
        conn.commit()
        conn.close()
        
        # Add to state
        state["vocabularies"].append({"id": vocab_id, "name": name, "code": code})
        log(f"Created vocabulary: {name} ({code})")
        
        return jsonify({"success": True, "id": vocab_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/create_term', methods=['POST'])
def api_create_term():
    """Create a new vocabulary term."""
    data = request.json
    vocabulary_id = data.get('vocabulary_id', '').strip()
    term = data.get('term', '').strip()
    code = data.get('code', '').strip()
    
    if not vocabulary_id or not term:
        return jsonify({"success": False, "error": "موضوع و نام برچسب الزامی است"})
    
    if not code:
        code = ''.join(word.capitalize() for word in term.split())
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check vocabulary exists
        cur.execute("SELECT id, name FROM masterdata_vocabulary WHERE id = %s", (vocabulary_id,))
        vocab = cur.fetchone()
        if not vocab:
            conn.close()
            return jsonify({"success": False, "error": "موضوع یافت نشد"})
        
        term_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO masterdata_vocabularyterm (id, vocabulary_id, term, code, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, true, NOW(), NOW())
        """, (term_id, vocabulary_id, term, code))
        conn.commit()
        conn.close()
        
        # Add to state
        state["terms"].append({
            "id": term_id, 
            "term": term, 
            "code": code,
            "vocabulary_id": vocabulary_id,
            "vocabulary_name": vocab["name"]
        })
        state["valid_term_ids"].add(term_id)
        log(f"Created term: {term} in {vocab['name']}")
        
        return jsonify({"success": True, "id": term_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/approve', methods=['POST'])
def api_approve():
    data = request.json
    saved_tags, saved_terms = save_approved_batch(data)
    state["current_results"] = None
    # Refresh term list if new terms were added
    if saved_terms > 0:
        load_vocabularies_and_terms()
    
    # Check if prefetch is ready
    has_prefetch = state["prefetch_status"] == "ready" and state["prefetch_results"] is not None
    return jsonify({
        "success": True, 
        "saved_tags": saved_tags, 
        "saved_terms": saved_terms,
        "has_prefetch": has_prefetch
    })

@app.route('/api/use_prefetch', methods=['POST'])
def api_use_prefetch():
    """Use pre-fetched results for next batch."""
    if state["prefetch_status"] != "ready" or state["prefetch_results"] is None:
        return jsonify({"success": False, "error": "No prefetch available"})
    
    # Move prefetch to current
    state["current_batch"] = state["prefetch_results"]["batch_number"]
    state["current_results"] = {
        'units': state["prefetch_results"]["units"],
        'new_terms': state["prefetch_results"]["new_terms"],
        'raw_results': state["prefetch_results"]["raw_results"]
    }
    state["status"] = "waiting_approval"
    
    # Clear prefetch and start new prefetch
    state["prefetch_results"] = None
    state["prefetch_status"] = "idle"
    
    # Start prefetching next batch
    prefetch_thread = threading.Thread(target=prefetch_next_batch)
    prefetch_thread.daemon = True
    prefetch_thread.start()
    
    log(f"Using pre-fetched batch {state['current_batch']}")
    return jsonify({"success": True})

@app.route('/api/prefetch_status')
def api_prefetch_status():
    """Get prefetch status."""
    return jsonify({
        "status": state["prefetch_status"],
        "ready": state["prefetch_status"] == "ready"
    })

@app.route('/api/skip', methods=['POST'])
def api_skip():
    state["status"] = "idle"
    state["current_results"] = None
    state["prefetch_results"] = None
    state["prefetch_status"] = "idle"
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
