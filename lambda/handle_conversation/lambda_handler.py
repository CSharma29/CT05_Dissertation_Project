import json
import os
import boto3
import logging
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("CT05_Store_Context")
lambda_client = boto3.client("lambda")

ORCHESTRATE_FUNCTION_NAME = os.environ.get(
    "ORCHESTRATE_FUNCTION_NAME", "CT05_Orchestrate_Conversation"
)
# Lex session attributes count towards the sessionState size limit, so
# keep the rolling in-session history bounded.
MAX_CONTEXT_SUMMARY_LENGTH = 4000

MESSAGE_DICT = {
    "welcome_message": "Welcome to the CT05 Intelligent Contact Centre. Can you please provide your customer ID?",
    "user_id_validated": "Thanks your user id has been validated. How can I assist you today?",
    "user_id_invalid": "I'm sorry I'm unable to find your userid in our system, Please provide a valid user id to continue.",
    "intent_not_found": "I'm sorry I didn't understand that. Can you please rephrase?",
    "general_fallback_message": "I'm sorry I couldn't understand that. Can you please share your user_id to continue?",
    "goodbye_message": "Thanks for contacting the CT05 Intelligent Contact Centre. Goodbye!",
    "llm_error_message": "I'm sorry, I'm having trouble answering that right now. Please try again.",
}


def lambda_handler(event, context):
    returnJson = {}
    intent_name = event["interpretations"][0]["intent"]["name"]
    session_attributes = event.get("sessionState", {}).get("sessionAttributes") or {}
    logger.debug(f"Event: {json.dumps(event)}")
    if intent_name == "CloseIntent":
        returnJson = handle_close_intent(event)
    elif session_attributes.get("user_verified") == "true":
        returnJson = handle_verified_user_query(event, session_attributes)
    elif intent_name == "WelcomeUserIntent":
        returnJson = handle_welcome_intent(event)
    elif intent_name == "ValidateUserIntent":
        returnJson = handle_validate_user_intent(event)
    elif intent_name == "FallbackIntent":
        returnJson = handle_fallback_intent(event)
    else:
        logger.debug("Unhandled intent")
        returnJson = close(MESSAGE_DICT["intent_not_found"])
    return returnJson


def handle_welcome_intent(event):
    return elicit_slot(
        "ValidateUserIntent",
        "UserIdentifier",
        MESSAGE_DICT["welcome_message"],
    )


def handle_validate_user_intent(event):
    slots = event["interpretations"][0]["intent"]["slots"]
    user_id_slot = slots.get("UserIdentifier")
    user_id = (
        user_id_slot["value"]["originalValue"] if user_id_slot else None
    )

    if not user_id:
        return elicit_slot(
            "ValidateUserIntent",
            "UserIdentifier",
            MESSAGE_DICT["user_id_invalid"],
        )

    context_summaries = fetch_context_summaries(user_id)
    if context_summaries is None:
        return elicit_slot(
            "ValidateUserIntent",
            "UserIdentifier",
            MESSAGE_DICT["user_id_invalid"],
        )

    session_attributes = {
        "user_id": user_id,
        "user_verified": "true",
        "context_summary": "\n".join(context_summaries),
    }
    return close(
        MESSAGE_DICT["user_id_validated"],
        intent_name="ValidateUserIntent",
        session_attributes=session_attributes,
    )


def handle_verified_user_query(event, session_attributes):
    """Route a verified user's utterance to the orchestrate_conversation
    Lambda, regardless of which intent Lex matched, and relay the LLM's
    reply while keeping the session open for the next question."""
    message = (event.get("inputTranscript") or "").strip()
    if not message:
        return elicit_intent(MESSAGE_DICT["intent_not_found"], session_attributes)

    payload = {
        "user_id": session_attributes.get("user_id"),
        "message": message,
        "context_summary": session_attributes.get("context_summary", ""),
    }
    try:
        response = lambda_client.invoke(
            FunctionName=ORCHESTRATE_FUNCTION_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode("utf-8"),
        )
        result = json.loads(response["Payload"].read())
    except (ClientError, json.JSONDecodeError):
        logger.exception("Failed to invoke orchestrate_conversation")
        return elicit_intent(MESSAGE_DICT["llm_error_message"], session_attributes)

    if not isinstance(result, dict) or result.get("statusCode") != 200 or not result.get("reply"):
        logger.error(f"orchestrate_conversation returned an error: {result}")
        return elicit_intent(MESSAGE_DICT["llm_error_message"], session_attributes)

    reply = result["reply"]
    session_attributes["context_summary"] = append_exchange(
        session_attributes.get("context_summary", ""), message, reply
    )
    return elicit_intent(reply, session_attributes)


def append_exchange(context_summary, message, reply):
    """Add the latest exchange to the in-session history so follow-up
    questions carry conversational context, trimming oldest text first."""
    exchange = f"User: {message} | Assistant: {reply}"
    combined = f"{context_summary}\n{exchange}" if context_summary else exchange
    return combined[-MAX_CONTEXT_SUMMARY_LENGTH:]


def handle_close_intent(event):
    return close(MESSAGE_DICT["goodbye_message"], intent_name="CloseIntent")


def handle_fallback_intent(event):
    return elicit_intent(MESSAGE_DICT.get("general_fallback_message", "this is a fallback message"))


def fetch_context_summaries(user_id):
    """Query CT05_Store_Context by user_id. Returns a list of context
    summaries (empty list if the user has none), or None if the user_id
    does not exist in the table or the query fails."""
    try:
        response = table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
    except ClientError:
        logger.exception(f"DynamoDB query failed for user_id: {user_id}")
        return None

    items = response.get("Items", [])
    logger.debug(f"Found {len(items)} context items for user_id: {user_id}")
    if not items:
        return None
    return [item["context_summary"] for item in items if item.get("context_summary")]


def elicit_slot(intent_name, slot_to_elicit, message):
    return {
        "sessionState": {
            "dialogAction": {
                "type": "ElicitSlot",
                "slotToElicit": slot_to_elicit,
            },
            "intent": {
                "name": intent_name,
                "state": "InProgress",
            },
        },
        "messages": [
            {"contentType": "PlainText", "content": message}
        ],
    }


def close(message, intent_name="FallbackIntent", session_attributes=None):
    return {
        "sessionState": {
            "sessionAttributes": session_attributes or {},
            "dialogAction": {
                "type": "Close",
            },
            "intent": {
                "name": intent_name,
                "state": "Fulfilled",
            },
        },
        "messages": [
            {"contentType": "PlainText", "content": message}
        ],
    }


def elicit_intent(message, session_attributes=None):
    return {
        "sessionState": {
            "sessionAttributes": session_attributes or {},
            "dialogAction": {
                "type": "ElicitIntent",
            },
        },
        "messages": [
            {"contentType": "PlainText", "content": message}
        ],
    }

