from temporalio import activity
import httpx
import json
import re

@activity.defn
async def extract_submission_activity(data: dict) -> dict:
    raw_text = data.get("raw_text", "")
    
    # Strip PII
    raw_text = re.sub(r'\d{10}', '[REDACTED PHONE]', raw_text)
    raw_text = re.sub(r'\d{4}\s\d{4}\s\d{4}', '[REDACTED AADHAAR]', raw_text)
    
    # Mock LLM API Call
    # Uses httpx for openrouter
    
    return {
        "title": "Extracted Title",
        "summary": raw_text[:50],
        "category": "Infrastructure",
        "severity": 3,
        "location_hint": "Unknown"
    }

@activity.defn
async def batch_extract_and_embed_activity(data: dict) -> dict:
    return {"count": 10}
