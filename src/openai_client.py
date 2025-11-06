import os, json, asyncio, httpx
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "40"))

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
}


async def create_response(payload: dict) -> dict:
    backoff_seconds = 2
    timeout = httpx.Timeout(TIMEOUT, read=TIMEOUT, connect=TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(6):
            try:
                r = await client.post(OPENAI_URL, headers=HEADERS, json=payload)
            except (httpx.ReadTimeout, httpx.ConnectError) as e:
                if attempt < 5:
                    await asyncio.sleep(backoff_seconds)
                    backoff_seconds *= 2
                    continue
                raise

            # Retry on common transient status codes
            if r.status_code in {429, 500, 502, 503, 504} and attempt < 5:
                await asyncio.sleep(backoff_seconds)
                backoff_seconds *= 2
                continue

            if r.status_code != 200:
                print(f"OpenAI API Error {r.status_code}: {r.text}")
            r.raise_for_status()
            return r.json()
    raise RuntimeError("OpenAI request failed repeatedly")


def build_payload(system_prompt: str, user_obj: dict, schema: dict, extra_text_blocks: list[str] | None = None) -> dict:
    user_content = json.dumps(user_obj, ensure_ascii=False)
    if extra_text_blocks:
        user_content += "\n\n" + "\n\n".join(extra_text_blocks)

    return {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "Scorecard", "schema": schema, "strict": True},
        },
    }


def extract_output_text(resp_json: dict) -> str:
    # Extract from Chat Completions API response
    choices = resp_json.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        return message.get("content", "")
    return json.dumps(resp_json, ensure_ascii=False)
