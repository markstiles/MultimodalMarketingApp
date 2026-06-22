"""HeadlessRunner — orchestrates DriverLLM + HeadlessSession in a turn loop."""
import logging
import re
from dataclasses import dataclass, field

from app.headless.context import ProxyContext, load_proxy_context
from app.headless.driver import ATTACH_MARKER, DONE_SIGNAL, DriverLLM
from app.headless.files import FileRegistry
from app.headless.session import HeadlessSession

logger = logging.getLogger(__name__)

_ATTACH_RE = re.compile(r"\[ATTACH:\s*([^\]]+)\]")


@dataclass
class TurnRecord:
    turn: int
    user_message: str
    assistant_response: str
    tool_calls: list[str] = field(default_factory=list)
    canvas_reload: bool = False
    attached_files: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    scenario: str
    turns: list[TurnRecord]
    completed: bool
    total_turns: int
    context: ProxyContext

    def summary(self) -> str:
        status = "completed" if self.completed else f"stopped after {self.total_turns} turns"
        tools_used = sorted({t for r in self.turns for t in r.tool_calls})
        return (
            f"Scenario {status}. "
            f"{self.total_turns} turns. "
            f"Tools used: {', '.join(tools_used) or 'none'}."
        )


class HeadlessRunner:
    """Runs a complete headless conversation from scenario to completion."""

    def __init__(
        self,
        scenario: str,
        max_turns: int = 20,
        files_source: str | None = None,
        verbose: bool = False,
    ):
        self.scenario = scenario
        self.max_turns = max_turns
        self.verbose = verbose

        self.context = load_proxy_context()
        self.files = FileRegistry(files_source)
        self.session = HeadlessSession(self.context)
        self.driver = DriverLLM(scenario, file_listing=self.files.format_listing())

    async def run(self) -> RunResult:
        history: list[dict] = []
        records: list[TurnRecord] = []
        completed = False

        logger.info("Starting headless run. context=%s", self.context.summary())
        if self.verbose:
            print(f"[headless] Context: {self.context.summary()}")
            print(f"[headless] Scenario: {self.scenario}\n")

        for turn_num in range(1, self.max_turns + 1):
            driver_message = await self.driver.next_message(history)

            if driver_message.strip() == DONE_SIGNAL or DONE_SIGNAL in driver_message:
                logger.info("Driver signalled completion on turn %d", turn_num)
                if self.verbose:
                    print(f"[headless] Driver signalled [DONE] after turn {turn_num - 1}")
                completed = True
                break

            user_message, attached_files = self._process_message(driver_message)

            if self.verbose:
                print(f"[turn {turn_num}] USER: {user_message[:200]}")
                if attached_files:
                    print(f"           FILES: {', '.join(attached_files)}")

            turn_result = await self.session.send(user_message)

            if self.verbose:
                print(f"[turn {turn_num}] ASSISTANT: {turn_result.response[:200]}")
                if turn_result.tool_calls:
                    print(f"           TOOLS: {', '.join(turn_result.tool_calls)}")
                print()

            history.append({"role": "user", "content": driver_message})
            history.append({"role": "assistant", "content": turn_result.response})

            records.append(
                TurnRecord(
                    turn=turn_num,
                    user_message=driver_message,
                    assistant_response=turn_result.response,
                    tool_calls=turn_result.tool_calls,
                    canvas_reload=turn_result.canvas_reload,
                    attached_files=attached_files,
                )
            )

            logger.info(
                "Turn %d complete. tools=%s canvas_reload=%s",
                turn_num,
                turn_result.tool_calls,
                turn_result.canvas_reload,
            )

        else:
            logger.warning("Max turns (%d) reached without [DONE] signal", self.max_turns)
            if self.verbose:
                print(f"[headless] Max turns ({self.max_turns}) reached")

        return RunResult(
            scenario=self.scenario,
            turns=records,
            completed=completed,
            total_turns=len(records),
            context=self.context,
        )

    def _process_message(self, message: str) -> tuple[str, list[str]]:
        """Replace [ATTACH: filename] markers with file contents.

        Text files are injected inline. Binary files get a descriptive notice.
        Returns (processed_message, list_of_attached_names).
        """
        attached: list[str] = []
        result = message

        for match in _ATTACH_RE.finditer(message):
            marker = match.group(0)
            name = match.group(1).strip()
            attached.append(name)

            text = self.files.read_text(name)
            if text is not None:
                replacement = f"\n\n--- {name} ---\n{text}\n--- end {name} ---"
                result = result.replace(marker, replacement)
                continue

            b64_result = self.files.read_b64(name)
            if b64_result is not None:
                _, mime = b64_result
                path = self.files.get_path(name)
                size_kb = (path.stat().st_size // 1024) if path else 0
                notice = f"[File attached: {name}, type={mime}, size={size_kb}KB — binary; request upload if needed]"
                result = result.replace(marker, notice)
                continue

            result = result.replace(marker, f"[File not found: {name}]")

        return result, attached
