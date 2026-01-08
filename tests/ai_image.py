#!/usr/bin/env python3
"""
Legal Document Image Processor with Multi-page Support
========================================================
Processes images of legal documents (رای وحدت رویه) using AI vision,
extracts structured information, and provides a web interface for review.

Features:
- Multi-page document detection and merging
- Incomplete document handling across batches
- Dual API support with automatic retry and fallback
- Auto-processing of next batch after approval
- Shamsi to Gregorian date conversion

Usage:
1. Create config.py with API keys (not committed to git)
2. Place JPG images in jpg/ subdirectory
3. Run: python ai_image.py
4. Open http://localhost:5001 in your browser
"""

VERSION = "1.2.0"

# ============================================
# CONFIGURATION
# ============================================

# API Configuration
API_CONFIGS = [
    {
        "name": "GapGPT",
        "api_key": "sk-o92MoYgtEGcJrtvYEPS8t3BTWCwUfdg6o3HzdA67L3yWtddO",
        "base_url": "https://api.gapgpt.app/v1"
    },
    {
        "name": "OpenAI",
        "api_key": "sk-proj-your-key-here",
        "base_url": "https://api.openai.com/v1"
    }
]

# Database Configuration
DB_CONFIG = {
    "host": "45.92.219.229",
    "port": 15432,
    "database": "ingest",
    "user": "ingest",
    "password": "rQXRweJEjVSD7tMKX4TrV3LQHDNhklt2"
}

# Model Settings
MODEL_NAME = "gpt-4.1-mini"
BATCH_SIZE = 10

# ============================================
# DO NOT MODIFY BELOW THIS LINE
# ============================================

import os
import json
import uuid
import base64
import re
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI
import jdatetime

app = Flask(__name__)

# Global state
state = {
    "status": "idle",  # idle, processing, waiting_approval
    "current_batch": 0,
    "total_images": 0,
    "processed_images": 0,
    "current_images": [],
    "current_results": None,
    "incomplete_entry": None,  # Store incomplete entry to continue in next batch
    "logs": [],
    "script_dir": os.path.dirname(os.path.abspath(__file__)),
    "jpg_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "jpg"),
    "api_index": 0  # Track which API to use next (alternates)
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

def build_vision_prompt(image_files):
    """Build prompt for GPT Vision with actual filenames."""
    system = """تو یک Legal Document Extractor هستی. تصاویر رای‌های وحدت رویه هیأت عمومی دیوان عالی کشور را تحلیل می‌کنی.

## ساختار تصاویر:
- سطر اول: رای شماره: [تاریخ شمسی] - [شماره رای]
  مثال: "رای شماره: 1346/4/22 - 123" یا "رای شماره: 1346/4/22-123"
  **مهم**: فرمت دقیق "تاریخ - شماره" است (تاریخ اول، شماره دوم)
- سطر دوم: بسمه تعالی یا باسمه تعالی
- سطر سوم: رأی وحدت رویه هیأت عمومی دیوان عالی کشور
- متن اصلی رای (کامل و بدون حذف)
- سطر آخر: هیات عمومی دیوان عالی کشور (امضا)

**مهمترین نکته - شناسایی اتمام رای:**
امضای "هیات عمومی دیوان عالی کشور" نشانه پایان رای است.
- اگر این امضا در تصویر وجود دارد → رای کامل است
- اگر این امضا نیست → رای ناقص است و در تصویر بعدی ادامه دارد

## خروجی JSON (بدون هیچ متن اضافه):
{
  "results": [
    {
      "image_files": ["file1.jpg"] یا ["file1.jpg", "file2.jpg"],
      "title": "رأی وحدت رویه هیأت عمومی دیوان عالی کشور - [تاریخ شمسی] - [شماره رای]",
      "text_type": "رای",
      "content": "رای شماره: [فقط شماره رای]\n\n[تمام متن اصلی رای - کامل و بدون حذف]",
      "effective_date": "[تاریخ شمسی در فرمت YYYY/MM/DD]",
      "confidence": "[high/medium/low]",
      "is_complete": true
    }
  ],
  "incomplete": [
    {
      "image_files": ["last_file.jpg"],
      "partial_content": "...",
      "reason": "امضا ندارد - ادامه در تصویر بعدی"
    }
  ]
}

## نکات مهم:
1. **CRITICAL - استخراج شماره رای:**
   - فرمت در تصویر: "رای شماره: [تاریخ] - [شماره]"
   - مثال در تصویر: "رای شماره: 1346/4/22 - 123"
   - شماره رای = عدد بعد از خط تیره (123)
   - تاریخ = قبل از خط تیره (1346/4/22)
   - در content فقط بنویس: "رای شماره: 123" (بدون تاریخ)
2. **تاریخ و شماره رای:** در title به این فرمت بنویس: "رأی وحدت رویه هیأت عمومی دیوان عالی کشور - [تاریخ] - [شماره رای]"
   - مثال: "رأی وحدت رویه هیأت عمومی دیوان عالی کشور - 1346/4/22 - 123"
3. **effective_date:** فقط تاریخ (بدون شماره رای)
3. **محتوا:** تمام متن اصلی رای را کامل بنویس (هیچ چیز حذف نشود)
4. فقط این موارد از ابتدا/انتها حذف شوند:
   - بسمه تعالی (اگر در ابتدا باشد)
   - رأی وحدت رویه هیأت عمومی دیوان عالی کشور (اگر در ابتدا باشد)
   - هیأت عمومی دیوان عالی کشور (اگر در انتها به عنوان امضا باشد)
5. **CRITICAL - چند صفحه‌ای**: اگر تصویر بعدی ادامه همان رای است:
   - در image_files هر دو فایل را بنویس ([فایل اول, فایل دوم])
   - محتوای هر دو صفحه را ترکیب کن
   - is_complete = true بگذار (چون امضا دارد)
6. **CRITICAL - رای ناقص**: اگر آخرین تصویر امضا ندارد:
   - این رای را در results نگذار
   - آن را در incomplete بگذار
   - دلیل: "امضا ندارد - ادامه در تصویر بعدی"
7. **CRITICAL**: در فیلد image_files باید دقیقاً از نام فایل‌های زیر استفاده کنی (به ترتیب ارسال تصاویر)"""

    # Build filenames list for the prompt
    filenames_list = "\n".join([f"{i+1}. {fname}" for i, fname in enumerate(image_files)])
    
    user = f"""لطفاً تمام تصاویر زیر را تحلیل کن.

**نام فایل‌های تصاویر (به ترتیب پشت سر هم):**
{filenames_list}

**مهم:**
1. تصاویر به ترتیب پشت سر هم ارسال شده‌اند
2. بررسی کن آیا تصویر بعدی ادامه همان رای است یا رای جدید
3. اگر چند تصویر یک رای هستند و امضا دارند:
   - در image_files همه فایل‌ها را بنویس: ["file1.jpg", "file2.jpg", "file3.jpg"]
   - محتوای همه صفحات را ترکیب کن
   - is_complete = true
   - در results بگذار
4. اگر آخرین تصویر امضا ندارد (رای ناقص):
   - در incomplete بگذار (نه results)
   - محتوای تا اینجا را ذخیره کن
   - دلیل: "امضا ندارد - ادامه در تصویر بعدی"
5. در JSON خروجی، دقیقاً از همان نام فایل‌های بالا استفاده کن"""
    
    return system, user

def call_gpt_vision(image_files):
    """Call GPT Vision API to extract information from images with retry logic."""
    
    max_retries = 3
    retry_delay = 2  # seconds
    
    # Try current API first, then fallback to alternate
    apis_to_try = [state["api_index"], (state["api_index"] + 1) % len(API_CONFIGS)]
    
    for api_attempt, api_idx in enumerate(apis_to_try):
        api_config = API_CONFIGS[api_idx]
        log(f"Using API: {api_config['name']} (attempt {api_attempt + 1}/{len(apis_to_try)})")
        client = OpenAI(api_key=api_config["api_key"], base_url=api_config["base_url"])
        
        # Build messages once
        system, user = build_vision_prompt(image_files)
        messages = [{"role": "system", "content": system}]
        content = [{"type": "text", "text": user}]
        
        for img_file in image_files:
            img_path = os.path.join(state["jpg_dir"], img_file)
            base64_image = encode_image(img_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })
        
        messages.append({"role": "user", "content": content})
        log(f"Prepared {len(image_files)} images for API call")
        
        # Retry logic for this API
        for retry in range(max_retries):
            try:
                log(f"Sending request to API (retry {retry + 1}/{max_retries})...")
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=4096,
                    timeout=60.0
                )
        
                result = response.choices[0].message.content
                log(f"✓ Got response: {len(result)} chars")
                
                # Update API index for next call
                state["api_index"] = (api_idx + 1) % len(API_CONFIGS)
        
                # Extract JSON from response
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    json_str = json_match.group()
                elif result.strip().startswith('{'):
                    json_str = result.strip()
                else:
                    log(f"Warning: No JSON found in response")
                    return '{"results": []}'
                
                return json_str
                
            except Exception as e:
                error_msg = str(e)
                log(f"API Error: {type(e).__name__}: {error_msg}")
                
                if retry < max_retries - 1:
                    wait_time = retry_delay * (2 ** retry)  # exponential backoff
                    log(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    log(f"Max retries reached for {api_config['name']}")
                    if api_attempt < len(apis_to_try) - 1:
                        log(f"Switching to alternate API...")
                        break  # Try next API
                    else:
                        log(f"All APIs failed!")
                        raise Exception(f"All API attempts failed. Last error: {error_msg}")
    
    # Should not reach here
    raise Exception("Unexpected error in API call loop")

def process_next_batch():
    """Process next batch of images."""
    state["status"] = "processing"
    
    # Get unprocessed images
    all_images = get_jpg_images()
    
    # If no images, stop
    if not all_images:
        log("No more images to process!")
        state["status"] = "idle"
        return False
    
    # Calculate batch based on remaining images, not counter
    # This ensures we always process from the start of remaining images
    state["current_batch"] += 1
    batch_images = all_images[:BATCH_SIZE]  # Always take first BATCH_SIZE images
    
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
        
        # Parse JSON with error handling
        try:
            result = json.loads(response)
        except json.JSONDecodeError as e:
            log(f"JSON parsing error: {e}")
            log(f"Attempting to repair JSON...")
            # Try to extract valid JSON objects
            matches = re.findall(r'\{[^{}]*"image_files"[^{}]*\}', response, re.DOTALL)
            if matches:
                try:
                    repaired_json = '{"results": [' + ','.join(matches) + ']}'
                    result = json.loads(repaired_json)
                    log(f"Successfully repaired JSON with {len(matches)} results")
                except:
                    log(f"Failed to repair JSON, using empty results")
                    result = {"results": []}
            else:
                log(f"No valid results found in response")
                result = {"results": []}
        
        results = result.get("results", [])
        incomplete_entries = result.get("incomplete", [])
        
        log(f"Got {len(results)} complete results")
        if incomplete_entries:
            log(f"Warning: {len(incomplete_entries)} incomplete entries (will continue in next batch)")
            # Store incomplete entry for next batch
            state["incomplete_entry"] = incomplete_entries[0] if incomplete_entries else None
        
        # Build display data - handle multi-image entries
        display_data = []
        processed_images = set()
        
        for result in results:
            # Get image files for this result (can be single or multiple)
            image_files = result.get('image_files', [])
            if not image_files:
                # Fallback to old format
                image_files = [result.get('image_file', '')]
            
            # Read all images for this entry
            images_base64 = []
            for img_file in image_files:
                if img_file in batch_images:
                    processed_images.add(img_file)
                    img_path = os.path.join(state["jpg_dir"], img_file)
                    with open(img_path, "rb") as f:
                        images_base64.append({
                            "filename": img_file,
                            "base64": base64.b64encode(f.read()).decode('utf-8')
                        })
            
            if images_base64:
                display_data.append({
                    "image_files": image_files,
                    "images_base64": images_base64,
                    "title": result.get("title", ""),
                    "text_type": result.get("text_type", "رای"),
                    "content": result.get("content", ""),
                    "effective_date": result.get("effective_date", ""),
                    "confidence": result.get("confidence", "low")
                })
        
        # Add any unprocessed images as separate entries
        for img_file in batch_images:
            if img_file not in processed_images:
                img_path = os.path.join(state["jpg_dir"], img_file)
                with open(img_path, "rb") as f:
                    img_base64 = base64.b64encode(f.read()).decode('utf-8')
                
                display_data.append({
                    "image_files": [img_file],
                    "images_base64": [{"filename": img_file, "base64": img_base64}],
                    "title": f"رأی وحدت رویه هیأت عمومی دیوان عالی کشور - [تاریخ] - [شماره رای]",
                    "text_type": "رای",
                    "content": "",
                    "effective_date": "",
                    "confidence": "low"
                })
        
        # Add incomplete entries at the end with warning
        if incomplete_entries:
            for incomplete in incomplete_entries:
                incomplete_files = incomplete.get('image_files', [])
                images_base64 = []
                for img_file in incomplete_files:
                    if img_file in batch_images:
                        img_path = os.path.join(state["jpg_dir"], img_file)
                        with open(img_path, "rb") as f:
                            images_base64.append({
                                "filename": img_file,
                                "base64": base64.b64encode(f.read()).decode('utf-8')
                            })
                
                if images_base64:
                    display_data.append({
                        "image_files": incomplete_files,
                        "images_base64": images_base64,
                        "title": incomplete.get('title', 'رای ناقص - ادامه در دسته بعدی'),
                        "text_type": "رای",
                        "content": incomplete.get('partial_content', ''),
                        "effective_date": incomplete.get('effective_date', ''),
                        "confidence": "medium",
                        "is_incomplete": True,
                        "incomplete_reason": incomplete.get('reason', 'امضا ندارد')
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

def clean_content(content):
    """Remove only header/footer elements, preserve all legal content."""
    if not content:
        return ""
    
    cleaned = content
    
    # Remove quotes
    cleaned = cleaned.replace('"', '')
    
    # Remove "بسمه تعالی" or "باسمه تعالی" ONLY if at the very beginning
    cleaned = re.sub(r'^[\s\n]*(بسمه تعالی|باسمه تعالی)[\s\n]*', '', cleaned, flags=re.MULTILINE)
    
    # Remove "رأی وحدت رویه هیأت عمومی دیوان عالی کشور" ONLY if at the very beginning
    cleaned = re.sub(r'^[\s\n]*(رأی وحدت رویه هیأت عمومی دیوان عالی کشور)[\s\n]*', '', cleaned, flags=re.MULTILINE)
    
    # Remove "هیأت عمومی دیوان عالی کشور" or "هیات عمومی دیوان عالی کشور" ONLY if at the very end (signature)
    # Support both spellings: هیأت (with hamza) and هیات (without hamza)
    cleaned = re.sub(r'[\s\n]*(هیأت عمومی دیوان عالی کشور|هیات عمومی دیوان عالی کشور)[\s\n]*$', '', cleaned, flags=re.MULTILINE)
    
    # Clean up excessive whitespace but preserve paragraph structure
    cleaned = re.sub(r'\n\n\n+', '\n\n', cleaned)  # Max 2 newlines
    cleaned = cleaned.strip()
    
    return cleaned

def shamsi_to_gregorian(shamsi_date_str):
    """Convert Shamsi date (YYYY/MM/DD) to Gregorian date."""
    if not shamsi_date_str:
        return None
    
    try:
        parts = shamsi_date_str.split('/')
        if len(parts) != 3:
            return None
        
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        j_date = jdatetime.date(year, month, day)
        g_date = j_date.togregorian()
        return g_date.strftime('%Y-%m-%d')
    except:
        return None

def save_approved_batch(approved_data):
    """Save approved entries to database and delete image files."""
    state["status"] = "saving"
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get existing AI user (09000000000)
    cur.execute("SELECT id FROM auth_user WHERE username = '09000000000' LIMIT 1")
    ai_user = cur.fetchone()
    if not ai_user:
        log("ERROR: AI user 09000000000 not found in database!")
        conn.close()
        state["status"] = "idle"
        return 0, []
    
    ai_user_id = ai_user['id']
    
    saved_count = 0
    deleted_files = []
    files_to_delete = []  # Collect files to delete AFTER all saves succeed
    
    # Extract entries from the data dict
    entries = approved_data.get('entries', [])
    
    for entry in entries:
        if not entry.get('approved'):
            continue
        
        try:
            entry_id = str(uuid.uuid4())
            
            # Clean content
            raw_content = entry.get('content', '')
            cleaned_content = clean_content(raw_content)
            
            # Convert Shamsi to Gregorian
            shamsi_date = entry.get('effective_date', '')
            gregorian_date = shamsi_to_gregorian(shamsi_date)
            
            cur.execute("""
                INSERT INTO documents_textentry 
                (id, title, text_type, content, validity_start_date, original_filename, created_by_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                entry_id,
                entry.get('title', ''),
                'verdict',
                cleaned_content,
                gregorian_date,
                '',
                ai_user_id
            ))
            conn.commit()
            saved_count += 1
            log(f"Saved entry: {entry.get('title', '')[:50]}...")
            
            # Collect files to delete AFTER successful save
            # BUT: Don't delete if this entry is marked as incomplete
            image_files = entry.get('image_files', [])
            if not image_files:
                # Fallback to old format
                img_file = entry.get('image_file')
                if img_file:
                    image_files = [img_file]
            
            # Check if this is an incomplete entry (should not be deleted)
            is_incomplete = entry.get('is_incomplete', False)
            
            if not is_incomplete:
                files_to_delete.extend(image_files)
            else:
                log(f"Skipped deletion of incomplete entry images: {image_files}")
            
        except Exception as e:
            conn.rollback()
            log(f"Error saving entry: {e}")
    
    # NOW delete files AFTER all database operations succeeded
    for img_file in files_to_delete:
        if img_file:
            img_path = os.path.join(state["jpg_dir"], img_file)
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                    deleted_files.append(img_file)
                    log(f"Deleted image: {img_file}")
                except Exception as e:
                    log(f"Error deleting {img_file}: {e}")
    
    conn.close()
    state["processed_images"] += saved_count
    log(f"Saved {saved_count} entries, deleted {len(deleted_files)} files")
    
    # Clear incomplete entry after successful save
    state["incomplete_entry"] = None
    
    # Check if there are more images to process
    remaining_images = get_jpg_images()
    if remaining_images:
        log(f"Auto-starting next batch ({len(remaining_images)} images remaining)...")
        # Process next batch automatically
        state["status"] = "idle"  # Reset status before processing
        process_next_batch()
    else:
        log("All images processed!")
        state["status"] = "idle"
        state["incomplete_entry"] = None
    
    return saved_count, deleted_files

# HTML Template with buttons at bottom
HTML = """
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>پردازشگر تصاویر اسناد حقوقی v{{ version }}</title>
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
        
        #bottom-controls {
            display: none;
            position: sticky;
            bottom: 0;
            background: rgba(26, 26, 46, 0.95);
            padding: 20px;
            border-top: 2px solid rgba(0,212,255,0.3);
            justify-content: center;
            gap: 15px;
            z-index: 1000;
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
        </div>
        
        <div class="log-box" id="logs"></div>
        
        <div id="results"></div>
        
        <div id="bottom-controls" style="display: flex;">
            <button class="btn btn-success" onclick="approveBatch()">تأیید و ذخیره</button>
            <button class="btn btn-danger" onclick="skipBatch()">رد کردن</button>
        </div>
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
                document.getElementById('bottom-controls').style.display = 'none';
                document.getElementById('results').innerHTML = '';
            } else if (data.status === 'processing') {
                statusDiv.textContent = '⏳ در حال پردازش...';
                statusDiv.classList.add('status-processing');
                document.getElementById('btn-start').style.display = 'none';
            } else if (data.status === 'waiting_approval') {
                statusDiv.textContent = '✅ آماده برای بررسی و تأیید';
                statusDiv.classList.add('status-waiting');
                document.getElementById('btn-start').style.display = 'none';
                showResults(data.current_results);
                document.getElementById('bottom-controls').style.display = 'flex';
            }
            
            // Update logs
            const logsDiv = document.getElementById('logs');
            logsDiv.innerHTML = data.logs.slice(-10).map(l => `<div>${l}</div>`).join('');
            logsDiv.scrollTop = logsDiv.scrollHeight;
        }
        
        function showResults(results) {
            if (!results) return;
            
            const html = results.map((entry, idx) => {
                // Handle multi-image entries
                const images = entry.images_base64 || [{filename: entry.image_file, base64: entry.image_base64}];
                const imageFilesStr = entry.image_files ? entry.image_files.join(', ') : entry.image_file;
                const imageFilesJson = JSON.stringify(entry.image_files || [entry.image_file]);
                
                const imagesHtml = images.map(img => `
                    <div style="margin-bottom: 10px;">
                        <img src="data:image/jpeg;base64,${img.base64}" class="image-preview" alt="${img.filename}">
                        <div style="color: #aaa; font-size: 11px; margin-top: 5px; text-align: center;">${img.filename}</div>
                    </div>
                `).join('');
                
                const isIncomplete = entry.is_incomplete || false;
                const incompleteWarning = isIncomplete ? `
                    <div style="background: #ff6600; color: #000; padding: 8px; border-radius: 4px; margin-top: 10px; font-weight: bold; text-align: center;">
                        ⚠️ رای ناقص - ادامه در دسته بعدی<br>
                        <span style="font-size: 11px;">${entry.incomplete_reason || 'امضا ندارد'}</span><br>
                        <span style="font-size: 11px;">این عکس حذف نخواهد شد</span>
                    </div>
                ` : '';
                
                return `
                <div class="entry-card" ${isIncomplete ? 'style="border: 3px solid #ff6600;"' : ''}>
                    <div>
                        ${imagesHtml}
                        <div style="margin-top: 10px; text-align: center;">
                            <span class="confidence-badge confidence-${entry.confidence}">${entry.confidence}</span>
                            ${images.length > 1 ? `<div style="color: #00ff88; font-size: 12px; margin-top: 5px; font-weight: bold;">چند صفحه‌ای (${images.length} عکس)</div>` : ''}
                        </div>
                        ${incompleteWarning}
                    </div>
                    <div class="entry-form">
                        <div class="approve-checkbox">
                            <input type="checkbox" id="approve-${idx}" ${isIncomplete ? '' : 'checked'}>
                            <label for="approve-${idx}">${isIncomplete ? 'رد کردن (برای ادامه در دسته بعدی)' : 'تأیید و ذخیره این مورد'}</label>
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">عنوان:</label>
                            <input type="text" class="form-input" id="title-${idx}" value="${entry.title}">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">تاریخ شروع اعتبار (YYYY/MM/DD):</label>
                            <input type="text" class="form-input" id="effective_date-${idx}" value="${entry.effective_date}">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">محتوا:</label>
                            <textarea class="form-textarea" id="content-${idx}">${entry.content}</textarea>
                        </div>
                        
                        <input type="hidden" id="image_files-${idx}" value='${imageFilesJson}'>
                        <input type="hidden" id="is_incomplete-${idx}" value='${isIncomplete}'>
                    </div>
                </div>
                `;
            }).join('');
            
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
            // Disable button immediately to prevent duplicate clicks
            const saveBtn = document.querySelector('.btn-success');
            const skipBtn = document.querySelector('.btn-danger');
            if (saveBtn.disabled) return; // Already processing
            
            saveBtn.disabled = true;
            skipBtn.disabled = true;
            saveBtn.textContent = '⏳ در حال ذخیره...';
            
            // Show loading state
            const statusDiv = document.getElementById('status');
            statusDiv.textContent = '⏳ در حال ذخیره در دیتابیس...';
            statusDiv.className = 'status status-processing';
            
            const results = document.querySelectorAll('.entry-card');
            const entries = [];
            
            results.forEach((card, idx) => {
                const imageFilesStr = document.getElementById(`image_files-${idx}`).value;
                const imageFiles = JSON.parse(imageFilesStr);
                const isIncomplete = document.getElementById(`is_incomplete-${idx}`).value === 'true';
                
                entries.push({
                    approved: document.getElementById(`approve-${idx}`).checked,
                    image_files: imageFiles,
                    title: document.getElementById(`title-${idx}`).value,
                    content: document.getElementById(`content-${idx}`).value,
                    effective_date: document.getElementById(`effective_date-${idx}`).value,
                    is_incomplete: isIncomplete
                });
            });
            
            fetch('/api/approve', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({entries: entries})
            })
            .then(r => r.json())
            .then(data => {
                // Re-enable buttons after save completes
                saveBtn.disabled = false;
                skipBtn.disabled = false;
                saveBtn.textContent = 'تأیید و ذخیره';
                
                updateUI(data);
                // Start polling to catch the auto-started next batch
                startPolling();
            })
            .catch(err => {
                // Re-enable buttons on error
                saveBtn.disabled = false;
                skipBtn.disabled = false;
                saveBtn.textContent = 'تأیید و ذخیره';
                statusDiv.textContent = '❌ خطا در ذخیره';
                statusDiv.className = 'status status-idle';
            });
        }
        
        function skipBatch() {
            fetch('/api/skip', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    updateUI(data);
                });
        }
        
        function startPolling() {
            if (pollInterval) clearInterval(pollInterval);
            pollInterval = setInterval(() => {
                fetch('/api/status')
                    .then(r => r.json())
                    .then(data => {
                        updateUI(data);
                        // Stop polling when idle or waiting for approval
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
    
    # Clear previous results
    state["current_results"] = None
    
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
    try:
        log(f"Approve request received. Current status: {state['status']}")
        
        data = request.json
        log(f"Approve data: {len(data.get('entries', []))} entries")
        
        # Save synchronously (no threading to avoid duplicate saves)
        saved_count, deleted_files = save_approved_batch(data)
        log(f"Save completed: {saved_count} entries, {len(deleted_files)} files deleted")
        
        # Update image count
        all_images = get_jpg_images()
        state["total_images"] = len(all_images)
        
        return jsonify({
            "status": state["status"],
            "current_batch": state["current_batch"],
            "total_images": state["total_images"],
            "processed_images": state["processed_images"],
            "logs": state["logs"][-20:],
            "saved_count": saved_count
        })
    except Exception as e:
        log(f"ERROR in api_approve: {e}")
        import traceback
        log(traceback.format_exc())
        state["status"] = "idle"
        return jsonify({"error": str(e)}), 500

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
