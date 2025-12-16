#!/usr/bin/env python3
"""Check database for unit types and terms."""
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": "45.92.219.229",
    "port": 15432,
    "database": "ingest",
    "user": "ingest",
    "password": "rQXRweJEjVSD7tMKX4TrV3LQHDNhklt2"
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Check unit types
print("=== Unit Types ===")
cur.execute("""
    SELECT unit_type, COUNT(*) as cnt 
    FROM documents_legalunit 
    WHERE content IS NOT NULL AND content != '' 
    GROUP BY unit_type 
    ORDER BY cnt DESC
""")
for row in cur.fetchall():
    print(f"{row['unit_type']}: {row['cnt']}")

# Check terms count
cur.execute("SELECT COUNT(*) as cnt FROM masterdata_vocabularyterm WHERE is_active = true")
print(f"\n=== Terms Count: {cur.fetchone()['cnt']} ===")

# Sample content for valid types
print("\n=== Sample Content ===")
cur.execute("""
    SELECT id, unit_type, LEFT(content, 300) as content_preview
    FROM documents_legalunit 
    WHERE content IS NOT NULL AND content != ''
      AND unit_type IN ('همه متن', 'ماده', 'بند', 'زیر بند', 'تبصره')
    LIMIT 3
""")
for row in cur.fetchall():
    print(f"ID: {row['id']}")
    print(f"Type: {row['unit_type']}")
    print(f"Content: {row['content_preview']}...")
    print("---")

# Sample terms
print("\n=== Sample Terms ===")
cur.execute("""
    SELECT vt.id, vt.term, v.name as vocab_name, v.code as vocab_code
    FROM masterdata_vocabularyterm vt
    JOIN masterdata_vocabulary v ON vt.vocabulary_id = v.id
    WHERE vt.is_active = true
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"{row['vocab_name']} ({row['vocab_code']}): {row['term']}")

conn.close()
