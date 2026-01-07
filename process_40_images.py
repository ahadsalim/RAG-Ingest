#!/usr/bin/env python3
"""
ONE-TIME: Process 40 uploaded images from /srv/tests/jpg
Check duplicates and save only new entries to database.
"""

import os
import sys

# Setup Django path
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ingest.settings')

import django
django.setup()

import json
import uuid
import base64
import re
from datetime import datetime
from django.contrib.auth.models import User
from ingest.apps.documents.models import TextEntry
from openai import OpenAI
import jdatetime

# Configuration
JPG_DIR = "/app/tests/jpg"
BATCH_SIZE = 10

# API Config
API_KEY = "sk-o92MoYgtEGcJrtvYEPS8t3BTWCwUfdg6o3HzdA67L3yWtddO"
API_BASE = "https://api.gapgpt.app/v1"
MODEL = "gpt-4.1-mini"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def call_ai(image_files):
    """Call AI to extract content."""
    client = OpenAI(api_key=API_KEY, base_url=API_BASE)
    
    system = """تو یک Legal Document Extractor هستی. از تصاویر رای‌های وحدت رویه، اطلاعات را استخراج کن.

خروجی JSON:
{
  "results": [
    {
      "image_files": ["file.jpg"],
      "title": "رأی وحدت رویه هیأت عمومی دیوان عالی کشور - [تاریخ]",
      "content": "رای شماره: [شماره]\\n\\n[متن کامل رای]",
      "effective_date": "[YYYY/MM/DD]"
    }
  ]
}

نکات:
- محتوا کامل باشد (هیچ چیز حذف نشود)
- فقط بسمله، عنوان و امضا از ابتدا/انتها حذف شود
- تاریخ فقط در title و effective_date"""
    
    filenames = "\n".join([f"{i+1}. {f}" for i, f in enumerate(image_files)])
    user = f"تصاویر:\n{filenames}\n\nاطلاعات را استخراج کن."
    
    messages = [{"role": "system", "content": system}]
    content = [{"type": "text", "text": user}]
    
    for img_file in image_files:
        img_path = os.path.join(JPG_DIR, img_file)
        b64 = encode_image(img_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })
    
    messages.append({"role": "user", "content": content})
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=4096,
        timeout=120.0
    )
    
    result = response.choices[0].message.content
    match = re.search(r'\{[\s\S]*\}', result)
    if match:
        return json.loads(match.group())
    return {"results": []}

def clean_content(content):
    if not content:
        return ""
    cleaned = content.replace('"', '')
    cleaned = re.sub(r'^[\s\n]*(بسمه تعالی|باسمه تعالی)[\s\n]*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'^[\s\n]*(رأی وحدت رویه هیأت عمومی دیوان عالی کشور)[\s\n]*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'[\s\n]*(هیأت عمومی دیوان عالی کشور)[\s\n]*$', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\n\n\n+', '\n\n', cleaned)
    return cleaned.strip()

def shamsi_to_gregorian(date_str):
    if not date_str:
        return None
    try:
        parts = date_str.split('/')
        if len(parts) != 3:
            return None
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        return jdatetime.date(y, m, d).togregorian()
    except:
        return None

def content_exists(content_snippet):
    """Check if content exists in DB."""
    snippet = content_snippet[:200].strip()
    if len(snippet) < 50:
        return False
    
    existing = TextEntry.objects.filter(content__icontains=snippet).first()
    if existing:
        log(f"  → Duplicate: {existing.title[:50]}...")
        return True
    return False

def main():
    log("=" * 60)
    log("ONE-TIME: Processing 40 images from /srv/tests/jpg")
    log("=" * 60)
    
    # Get AI user
    ai_user = User.objects.filter(username='09000000000').first()
    if not ai_user:
        log("ERROR: User 09000000000 not found!")
        return
    
    # Get images
    images = sorted([f for f in os.listdir(JPG_DIR) if f.lower().endswith('.jpg')])
    log(f"Found {len(images)} images")
    
    saved = 0
    skipped = 0
    deleted = 0
    
    # Process in batches
    for i in range(0, len(images), BATCH_SIZE):
        batch = images[i:i+BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        
        log(f"\nBatch {batch_num}: {len(batch)} images")
        
        try:
            # Call AI
            result = call_ai(batch)
            results = result.get("results", [])
            log(f"Got {len(results)} results")
            
            for res in results:
                img_files = res.get('image_files', [])
                title = res.get('title', '')
                content = res.get('content', '')
                date_str = res.get('effective_date', '')
                
                cleaned = clean_content(content)
                
                # Check duplicate
                if content_exists(cleaned):
                    log(f"  SKIP: {title[:50]}...")
                    skipped += 1
                    for f in img_files:
                        path = os.path.join(JPG_DIR, f)
                        if os.path.exists(path):
                            os.remove(path)
                            deleted += 1
                    continue
                
                # Save
                entry = TextEntry(
                    title=title,
                    text_type='verdict',
                    content=cleaned,
                    validity_start_date=shamsi_to_gregorian(date_str),
                    created_by=ai_user
                )
                entry.save()
                saved += 1
                log(f"  SAVED: {title[:50]}...")
                
                # Delete images
                for f in img_files:
                    path = os.path.join(JPG_DIR, f)
                    if os.path.exists(path):
                        os.remove(path)
                        deleted += 1
                        log(f"  Deleted: {f}")
                        
        except Exception as e:
            log(f"ERROR: {e}")
            import traceback
            log(traceback.format_exc())
    
    log("\n" + "=" * 60)
    log(f"Saved: {saved} | Skipped: {skipped} | Deleted: {deleted} images")
    log("=" * 60)

if __name__ == '__main__':
    main()
