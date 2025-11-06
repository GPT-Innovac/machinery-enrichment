import json
from .schema import SCORECARD_SCHEMA
from .prompt import SYSTEM_PROMPT
from .openai_client import build_payload, create_response, extract_output_text


async def enrich_one(company_name: str, address: str, website: str | None, phone: str | None = None) -> dict:
    user_obj = {
        "company_name": company_name,
        "address": address,
        "website": website or "",
        "phone": phone or "",
    }

    # No web scraping - rely purely on ChatGPT's knowledge
    payload = build_payload(
        system_prompt=SYSTEM_PROMPT,
        user_obj=user_obj,
        schema=SCORECARD_SCHEMA,
        extra_text_blocks=None,  # No additional context needed
    )

    resp = await create_response(payload)
    text = extract_output_text(resp)
    try:
        return json.loads(text)
    except Exception:
        return {"_raw": text, "company_name": company_name, "address": address, "website": website}
