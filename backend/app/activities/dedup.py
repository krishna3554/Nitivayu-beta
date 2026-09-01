from temporalio import activity

@activity.defn
async def check_deduplication_activity(data: dict) -> dict:
    # Query pgvector placeholder
    # SELECT problem_id, 1 - (summary_embedding <=> $1) ...
    return {
        "is_duplicate": False,
        "duplicate_id": None
    }
