from temporalio import activity

@activity.defn
async def route_to_universities_activity(data: dict) -> dict:
    # S_semantic, S_theme, S_capacity, S_geo
    return {
        "top_3": ["Univ A", "Univ B", "Univ C"],
        "scores": {}
    }

@activity.defn
async def global_university_routing_activity(data: dict) -> dict:
    return {"status": "done"}
