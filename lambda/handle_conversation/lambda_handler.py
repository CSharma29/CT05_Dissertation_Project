import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("CT05_Store_Context")

MESSAGE_DICT = {
    "welcome_message": "Welcome to the CT05 Intelligent Contact Centre. Can you please provide your customer ID?",
    "user_id_validated": "Thanks your user id has been validated. How can I assist you today?",
    "user_id_invalid": "I'm sorry I'm unable to find your userid in our system would you like to continue as a new user?",
    "intent_not_found": "I'm sorry I didn't understand that. Can you please rephrase?",
    "general_fallback_message": "I'm sorry I couldn't understand that. Can you please share your user_id to continue?",
}


def lambda_handler(event, context):
    returnJson = {}
    intent_name = event["interpretations"][0]["intent"]["name"]
    logger.debug(f"Event: {json.dumps(event)}")
    if intent_name == "WelcomeUserIntent":
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
    user_id = event["interpretations"][0]["intent"]["slots"]["UserIdentifier"]["value"][
        "originalValue"
    ]

    if user_id:
        # store_user_id(event["sessionId"], user_id)
        return close(MESSAGE_DICT["user_id_validated"])
    else:
        return elicit_slot(
            "ValidateUserIntent",
            "UserIdentifier",
            MESSAGE_DICT["user_id_invalid"],
        )


def handle_fallback_intent(event):
    return elicit_intent(MESSAGE_DICT.get("general_fallback_message", "this is a fallback message"))


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


def close(message, intent_name="FallbackIntent"):
    return {
        "sessionState": {
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


def elicit_intent(message):
    return {
        "sessionState": {
            "dialogAction": {
                "type": "ElicitIntent",
            },
        },
        "messages": [
            {"contentType": "PlainText", "content": message}
        ],
    }


def store_user_id(session_id, user_id):
    table.put_item(Item={"UserId": user_id})
