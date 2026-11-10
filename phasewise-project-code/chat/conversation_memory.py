"""The last few exchanges of one person's own conversation, for the next prompt and search."""

from config import config
from persistence.models import ChatTurn
from persistence.repository import fetch_chat_turns


def recall_conversation(session, username, question_text):
    """History to read and words to search with, from this person's own recent turns."""
    turns = fetch_chat_turns(session, ChatTurn.username == username, config.CHAT_HISTORY_TURN_LIMIT)
    oldest_first = list(reversed(turns))
    if not oldest_first:
        history_text = config.CHAT_FIRST_QUESTION_TEXT
    else:
        exchanges = []
        for turn in oldest_first:
            answer = turn["answer_text"]
            if turn["question_type"] in config.CHAT_RECORD_TYPES:
                answer = config.CHAT_RECORD_ANSWER_IN_HISTORY
            exchanges.append(f"Question: {turn['question_text']}\nAnswer: {answer}")
        history_text = "\n\n".join(exchanges)
    previous_question = turns[0]["question_text"] if turns else ""
    search_text = f"{previous_question} {question_text}".strip() if previous_question else question_text
    return {
        "history_text": history_text,
        "search_text": search_text,
        "previous_question": previous_question,
    }
