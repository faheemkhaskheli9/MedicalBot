import json
import logging

from .llm_client import get_llm_provider

logger = logging.getLogger(__name__)

SUMMARIZE_THRESHOLD = 30
MESSAGES_TO_KEEP = 10

_COMPRESSION_PROMPT = (
    "You are a medical conversation memory assistant. "
    "Summarize the following patient-bot conversation excerpt into a concise running summary "
    "that a medical triage bot can use to maintain context. "
    "If an existing summary is provided, merge the new content into it.\n\n"
    "Respond ONLY with valid JSON in exactly this shape:\n"
    '{"summary": "<concise summary of the conversation so far>"}'
)


def summarize_session_if_needed(session) -> None:
    """Compress old triage messages into session.conversation_summary when threshold is exceeded."""
    unsummarized = list(
        session.messages.filter(is_summarized=False).order_by("created_at")
    )
    if len(unsummarized) <= SUMMARIZE_THRESHOLD:
        return

    to_summarize = unsummarized[: len(unsummarized) - MESSAGES_TO_KEEP]
    if not to_summarize:
        return

    conversation_text = "\n".join(
        f"{'PATIENT' if m.sender == 'patient' else 'BOT'}: {m.content}"
        for m in to_summarize
    )

    prior_block = (
        f"\n\nExisting summary to merge into:\n{session.conversation_summary}"
        if session.conversation_summary
        else ""
    )

    try:
        raw = get_llm_provider().complete([
            {"role": "system", "content": _COMPRESSION_PROMPT},
            {
                "role": "user",
                "content": f"Conversation:{prior_block}\n\nNew messages:\n{conversation_text}",
            },
        ])
        data = json.loads(raw)
        summary_text = data.get("summary", raw)
    except Exception:
        logger.exception("Triage session compression failed for session %s", session.id)
        return

    session.conversation_summary = summary_text
    session.save(update_fields=["conversation_summary"])

    ids_to_mark = [m.id for m in to_summarize]
    session.messages.filter(id__in=ids_to_mark).update(is_summarized=True)


def build_conversation_history(session) -> list[dict]:
    """
    Return conversation history for LangGraph: prepend summary context if present,
    then recent unsummarized messages.
    """
    recent = session.messages.filter(is_summarized=False).order_by("created_at")
    history = [
        {
            "role": "user" if m.sender == "patient" else "assistant",
            "content": m.content,
        }
        for m in recent
    ]
    if session.conversation_summary:
        history = [
            {
                "role": "system",
                "content": f"[Earlier conversation summary]\n{session.conversation_summary}",
            }
        ] + history
    return history
