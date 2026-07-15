import json
import logging
import os
import urllib.error
import urllib.request

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_SECRET_NAME = os.environ.get("LLM_SECRET_NAME", "CT05_LLM_Secret")
TABLE_NAME = os.environ.get("TABLE_NAME", "CT05_Store_Context")

DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash",
    "anthropic": "claude-opus-4-8",
}

SYSTEM_PROMPT = (
    "You are the assistant for the CT05 Intelligent Contact Centre. "
    "Answer the customer's query clearly and concisely. "
    "Use the conversation history provided to personalise your response."
)

# DynamoDB sort key values are limited to 1024 bytes
MAX_SUMMARY_LENGTH = 500
LLM_TIMEOUT_SECONDS = 25

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)
secrets_client = boto3.client("secretsmanager")

_api_key_cache = {}


def lambda_handler(event, context):
    logger.debug(f"Event: {json.dumps(event)}")
    user_id = event.get("user_id")
    message = event.get("message")
    context_summary = event.get("context_summary", "")

    if not user_id or not message:
        return {"statusCode": 400, "error": "user_id and message are required"}

    try:
        api_key = get_api_key(LLM_SECRET_NAME)
        reply = call_llm(message, context_summary, api_key)
    except Exception:
        logger.exception(f"LLM call failed (provider: {LLM_PROVIDER})")
        return {
            "statusCode": 502,
            "error": "Failed to get a response from the language model",
        }

    store_context_summary(user_id, message, reply)
    return {"statusCode": 200, "reply": reply}


def get_api_key(secret_name):
    """Fetch the LLM API key from Secrets Manager, cached across warm
    invocations. Supports secrets stored as raw strings or as JSON
    objects with an 'api_key' key (or a single key/value pair)."""
    if secret_name in _api_key_cache:
        return _api_key_cache[secret_name]

    response = secrets_client.get_secret_value(SecretId=secret_name)
    secret_string = response["SecretString"]

    try:
        secret_json = json.loads(secret_string)
        if isinstance(secret_json, dict):
            api_key = secret_json.get("api_key") or next(iter(secret_json.values()))
        else:
            api_key = secret_string
    except (json.JSONDecodeError, StopIteration):
        api_key = secret_string

    _api_key_cache[secret_name] = api_key
    return api_key


def call_llm(message, context_summary, api_key):
    model = LLM_MODEL or DEFAULT_MODELS.get(LLM_PROVIDER)
    if not model:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")

    if context_summary:
        user_content = (
            f"Previous conversation history for this customer:\n{context_summary}\n\n"
            f"Customer's current query:\n{message}"
        )
    else:
        user_content = message

    if LLM_PROVIDER == "gemini":
        return call_gemini(model, user_content, api_key)
    elif LLM_PROVIDER == "anthropic":
        return call_anthropic(model, user_content, api_key)
    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")


def call_gemini(model, user_content, api_key):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:generateContent"
    )
    headers = {"x-goog-api-key": api_key}
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
    }
    response = http_post_json(url, headers, body)
    return response["candidates"][0]["content"]["parts"][0]["text"]


def call_anthropic(model, user_content, api_key):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model": model,
        "max_tokens": 2048,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_content}],
    }
    response = http_post_json(url, headers, body)

    if response.get("stop_reason") == "refusal":
        logger.warning(f"Anthropic refusal: {response.get('stop_details')}")
        return "I'm sorry, I'm not able to help with that request."

    for block in response.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    raise ValueError("No text content in Anthropic response")


def http_post_json(url, headers, body):
    headers = {"Content-Type": "application/json", **headers}
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=LLM_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        logger.error(f"LLM API returned {e.code}: {error_body}")
        raise


def store_context_summary(user_id, message, reply):
    """Append this exchange to the user's conversation history. The
    summary is the table's sort key, so it must stay under 1024 bytes."""
    summary = f"User: {message} | Assistant: {reply}"[:MAX_SUMMARY_LENGTH]
    try:
        table.put_item(Item={"user_id": user_id, "context_summary": summary})
    except ClientError:
        logger.exception(f"Failed to store context summary for user_id: {user_id}")
