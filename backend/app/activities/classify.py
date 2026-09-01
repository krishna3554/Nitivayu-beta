from temporalio import activity

@activity.defn
async def classify_and_embed_activity(data: dict) -> dict:
    summary = data.get("summary", "")
    # Placeholder for sentence-transformers
    embedding = [0.1] * 384
    return {
        "top_category": "Infrastructure",
        "confidence": 0.95,
        "embedding": embedding
    }
