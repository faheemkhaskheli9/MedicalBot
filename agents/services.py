import json

from patient.llm_client import get_llm_provider

# How many unsummarized messages trigger a compression pass.
SUMMARIZE_THRESHOLD = 30
# How many recent messages to keep out of the summary (the "live" window).
MESSAGES_TO_KEEP = 10


def _call_llm(system_prompt: str, messages: list[dict]) -> str:
    return get_llm_provider().complete(
        [{"role": "system", "content": system_prompt}] + messages
    )


def _build_system_prompt(agent, session) -> str:
    parts = [agent.instructions.strip()]

    facts = list(agent.facts.values_list("fact", flat=True))
    if facts:
        bullet_facts = "\n".join(f"- {f}" for f in facts)
        parts.append(f"\n## Known Facts About the User\n{bullet_facts}")

    latest_summary = session.summaries.order_by("-created_at").first()
    if latest_summary:
        parts.append(f"\n## Previous Conversation Summary\n{latest_summary.content}")

    return "\n".join(parts)


def _get_recent_messages(session) -> list[dict]:
    msgs = session.messages.filter(is_summarized=False).order_by("created_at")
    return [{"role": m.role, "content": m.content} for m in msgs]


def summarize_if_needed(session) -> None:
    """Compress the oldest messages into a summary and extract durable facts."""
    from .models import AgentFact, ConversationSummary

    unsummarized = list(
        session.messages.filter(is_summarized=False).order_by("created_at")
    )
    if len(unsummarized) <= SUMMARIZE_THRESHOLD:
        return

    to_summarize = unsummarized[: len(unsummarized) - MESSAGES_TO_KEEP]
    if not to_summarize:
        return

    conversation_text = "\n".join(
        f"{m.role.upper()}: {m.content}" for m in to_summarize
    )

    previous_summary = session.summaries.order_by("-created_at").first()
    prior_block = (
        f"\n\nExisting summary to merge into:\n{previous_summary.content}"
        if previous_summary
        else ""
    )

    extraction_prompt = (
        "You are a conversation memory assistant. Given the conversation excerpt below, "
        "produce two things:\n"
        "1. A concise running summary of what was discussed. If an existing summary is "
        "provided, merge the new content into it rather than replacing it.\n"
        "2. A JSON list of durable, specific facts about the user revealed in the "
        "conversation (preferences, background, goals, constraints, names, etc.).\n\n"
        "Respond ONLY with valid JSON, exactly this shape:\n"
        '{"summary": "...", "facts": ["fact 1", "fact 2"]}'
    )

    raw = _call_llm(
        extraction_prompt,
        [
            {
                "role": "user",
                "content": f"Conversation:{prior_block}\n\nNew messages to process:\n{conversation_text}",
            }
        ],
    )

    try:
        data = json.loads(raw)
        summary_text = data.get("summary", raw)
        new_facts: list[str] = data.get("facts", [])
    except (json.JSONDecodeError, AttributeError):
        summary_text = raw
        new_facts = []

    ConversationSummary.objects.create(
        session=session,
        content=summary_text,
        messages_covered=len(to_summarize),
    )

    for fact_text in new_facts:
        if fact_text.strip():
            AgentFact.objects.create(
                agent=session.agent,
                fact=fact_text.strip(),
                source_session=session,
            )

    ids_to_mark = [m.id for m in to_summarize]
    session.messages.filter(id__in=ids_to_mark).update(is_summarized=True)


def send_message(session, user_content: str) -> str:
    """Persist user message, get LLM reply, persist reply, then compress if needed."""
    from .models import AgentMessage

    AgentMessage.objects.create(session=session, role="user", content=user_content)

    system_prompt = _build_system_prompt(session.agent, session)
    recent = _get_recent_messages(session)
    reply = _call_llm(system_prompt, recent)

    AgentMessage.objects.create(session=session, role="assistant", content=reply)

    summarize_if_needed(session)

    return reply
