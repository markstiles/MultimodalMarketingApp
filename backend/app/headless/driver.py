"""Driver LLM — simulates a marketing professional user.

Generates the next user message given the conversation history and the
scenario goal. Emits DONE_SIGNAL when it judges the scenario complete.
"""
import logging
import os

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

DONE_SIGNAL = "[DONE]"
ATTACH_MARKER = "[ATTACH:"

_SYSTEM_PROMPT = """\
You are simulating a marketing professional using an AI marketing pipeline tool.

## Your scenario goal
{scenario}

## Your persona
You are a knowledgeable, efficient marketer who:
- Provides specific, realistic details about the brand, campaign, and audience when the assistant asks
- Reviews generated content and either approves it with a short affirmative or requests one concrete improvement
- Keeps messages concise (2-3 sentences) — don't volunteer information the assistant didn't ask for
- Never asks clarifying questions about the scenario; you already know all the details
- Stays in character; never reference being an AI or running a test

## Available files
{files_section}

To attach a file in your message, include `[ATTACH: filename.ext]` on its own line. Text files
will have their content injected automatically. Binary files (PDF, DOCX) will be noted with
their metadata so the assistant can request an upload.

## Completion rule
When the primary deliverable has been confirmed saved to Sitecore (you see a success message
or a media library path in the assistant's response), output EXACTLY the following on a line
by itself — nothing else:
{done_signal}

Do not output {done_signal} prematurely. The scenario is only complete once the key artifact
is confirmed saved, not just drafted.
""".strip()


class DriverLLM:
    """Simulated user that drives a headless conversation toward a scenario goal."""

    def __init__(self, scenario: str, file_listing: str = "No files available."):
        self.scenario = scenario
        self._system_prompt = _SYSTEM_PROMPT.format(
            scenario=scenario,
            files_section=file_listing,
            done_signal=DONE_SIGNAL,
        )
        self._llm = self._build_llm()

    def _build_llm(self):
        from langchain_openai import ChatOpenAI

        kwargs: dict = {
            "api_key": os.environ["LLM_API_KEY"],
            "model": (
                os.environ.get("HEADLESS_DRIVER_MODEL")
                or os.environ.get("LLM_MODEL", "gpt-4o")
            ),
            "streaming": False,
            "temperature": 0.3,
        }
        base_url = os.environ.get("LLM_BASE_URL")
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

    def _format_history(self, history: list[dict]) -> str:
        if not history:
            return "(no messages yet — this is the start of the conversation)"
        lines = []
        for i, turn in enumerate(history, 1):
            speaker = "YOU" if turn["role"] == "user" else "ASSISTANT"
            # Truncate very long assistant responses to avoid overwhelming the context
            content = turn["content"]
            if turn["role"] == "assistant" and len(content) > 800:
                content = content[:800] + "… [truncated]"
            lines.append(f"[{i}] {speaker}: {content}")
        return "\n\n".join(lines)

    async def next_message(self, history: list[dict]) -> str:
        """Generate the next user message given the conversation so far.

        Returns DONE_SIGNAL if the scenario goal has been achieved.
        Returns a plain string message otherwise.
        """
        history_text = self._format_history(history)

        if not history:
            prompt = (
                "The conversation hasn't started yet. "
                "Send your opening message to begin working toward your goal."
            )
        else:
            prompt = (
                f"Conversation so far:\n\n{history_text}\n\n"
                "---\n"
                "Based on the conversation above, what do you say next? "
                f"If the scenario goal is fully complete, output only: {DONE_SIGNAL}"
            )

        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=prompt),
        ]

        result = await self._llm.ainvoke(messages)
        response = result.content.strip()
        logger.debug("Driver generated: %r", response[:120])
        return response
