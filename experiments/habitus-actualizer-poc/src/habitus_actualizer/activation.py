from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

from .contracts import AbilityId, AbilityRequest, SuppressedRequest


_ALIASES: dict[str, AbilityId] = {
    "change directory to": AbilityId.NAVIGATE,
    "navigate to": AbilityId.NAVIGATE,
    "go to": AbilityId.NAVIGATE,
    "enter": AbilityId.NAVIGATE,
    "list": AbilityId.LIST,
    "inspect": AbilityId.READ,
    "show": AbilityId.READ,
    "read": AbilityId.READ,
    "open": AbilityId.READ,
    "view": AbilityId.READ,
    "write": AbilityId.WRITE,
    "create": AbilityId.WRITE,
    "save": AbilityId.WRITE,
    "run": AbilityId.RUN,
    "execute": AbilityId.RUN,
    "launch": AbilityId.RUN,
}

_GERUNDS = {
    "entering": "enter",
    "executing": "execute",
    "inspecting": "inspect",
    "launching": "launch",
    "listing": "list",
    "navigating to": "navigate to",
    "opening": "open",
    "reading": "read",
    "running": "run",
    "saving": "save",
    "showing": "show",
    "viewing": "view",
    "writing": "write",
}
_VERB_FORMS = (*_ALIASES, *_GERUNDS)
_VERBS = "|".join(re.escape(alias) for alias in sorted(_VERB_FORMS, key=len, reverse=True))
_ACTION_LEAD_IN = (
    r"(?:(?:proceed|attempt|try)\s+(?:to|by)\s+)?"
    r"(?:directly\s+)?"
)
_COMMITMENT = re.compile(
    rf"(?ix)\b(?:"
    rf"i\s*(?:'ll|will|am\s+going\s+to|need\s+to)|"
    rf"let\s+me|"
    rf"next\s+i\s*(?:'ll|will)|"
    rf"now\s+i\s*(?:'ll|will)"
    rf")\s+{_ACTION_LEAD_IN}(?P<verb>{_VERBS})\b"
)
_CHAINED = re.compile(rf"(?ix)\b(?:and\s+then|then|and)\s+(?P<verb>{_VERBS})\b")
_QUOTED = re.compile(r"`([^`]+)`|\"([^\"]+)\"|'([^']+)'")
_FENCED_COMMAND = re.compile(
    r"(?is)```(?:bash|sh|shell)?[ \t]*\n(?P<body>.*?)```"
)


@dataclass(frozen=True)
class ActivationDraft:
    ability_id: AbilityId
    phrase: str
    verb: str
    arguments: Mapping[str, Any]
    confidence: float
    reasons: tuple[str, ...]


class NaturalLanguageActivator:
    """A conservative micro-grammar for ordinary assistant action statements."""

    def __init__(self, *, maximum_abilities: int = 3) -> None:
        if maximum_abilities < 1:
            raise ValueError("maximum_abilities must be positive")
        self.maximum_abilities = maximum_abilities

    @staticmethod
    def _canonical_verb(raw: str) -> str:
        value = raw.casefold().strip()
        return _GERUNDS.get(value, value)

    @staticmethod
    def _clean_tail(value: str) -> str:
        # Periods are meaningful in filenames and hidden paths. Sentence-final
        # punctuation is removed by the boundary pass before argument parsing.
        return value.strip(" \t\n,:;!?")

    @staticmethod
    def _quoted_values(value: str) -> list[str]:
        found: list[str] = []
        for match in _QUOTED.finditer(value):
            found.append(next(group for group in match.groups() if group is not None))
        return found

    @staticmethod
    def _fenced_command(value: str) -> str | None:
        matches = list(_FENCED_COMMAND.finditer(value))
        if len(matches) != 1:
            return None
        lines = [
            line.strip()
            for line in matches[0].group("body").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        return lines[0] if len(lines) == 1 else None

    @staticmethod
    def _unquoted_path(value: str, *, ability: AbilityId) -> str:
        target = value.strip()
        if ability == AbilityId.LIST and re.match(
            r"(?is)^(?:the\s+)?(?:contents\s+of\s+(?:the\s+)?)?(?:current|working)\s+directory\b",
            target,
        ):
            return "."
        target = re.sub(r"(?is)^(?:the\s+)?contents\s+of\s+", "", target)
        target = re.split(
            r"(?is)(?:,|\s+(?:to|so\s+that|in\s+order\s+to|before|after|because|as)\s+)",
            target,
            maxsplit=1,
        )[0]
        target = re.sub(r"(?is)^(?:the\s+)?(?:file|folder|directory)\s+", "", target)
        target = re.sub(r"(?is)\s+(?:file|folder|directory)\s*$", "", target)
        target = target.strip()
        if target.casefold() in {"it", "them", "these", "these items", "this", "those"}:
            return ""
        # Paths containing spaces must be quoted. Reject descriptive prose
        # rather than turning it into a bogus filesystem request.
        return target if not re.search(r"\s", target) else ""

    def _arguments(self, ability: AbilityId, verb: str, tail: str) -> dict[str, Any]:
        cleaned = self._clean_tail(tail)
        quoted = self._quoted_values(cleaned)
        if ability in {AbilityId.READ, AbilityId.LIST, AbilityId.NAVIGATE}:
            target = quoted[0] if quoted else self._unquoted_path(cleaned, ability=ability)
            target = re.sub(r"^(?:the\s+)?(?:file|folder|directory)\s+", "", target, flags=re.I)
            target = re.sub(r"^(?:at|in|inside|to)\s+", "", target, flags=re.I)
            key = "path"
            fallback = "." if ability == AbilityId.LIST else ""
            return {key: self._clean_tail(target) or fallback}
        if ability == AbilityId.RUN:
            command = quoted[0] if quoted else cleaned
            return {"command": self._clean_tail(command)}
        if ability == AbilityId.WRITE:
            patterns = (
                re.compile(r"(?is)^\s*[\"'`](.*?)[\"'`]\s+to\s+(.+)$"),
                re.compile(r"(?is)^\s*(.+?)\s+with\s+[\"'`](.*?)[\"'`]\s*$"),
                re.compile(r"(?is)^\s*[\"'`](.*?)[\"'`]\s+as\s+(.+)$"),
            )
            first = patterns[0].match(cleaned)
            if first:
                return {"content": first.group(1), "path": self._clean_tail(first.group(2))}
            second = patterns[1].match(cleaned)
            if second:
                return {"path": self._clean_tail(second.group(1)), "content": second.group(2)}
            third = patterns[2].match(cleaned)
            if third:
                return {"content": third.group(1), "path": self._clean_tail(third.group(2))}
            if len(quoted) >= 2:
                return {"content": quoted[0], "path": quoted[1]}
            return {"path": cleaned, "content": ""}
        return {}

    def _matches(self, text: str) -> list[tuple[int, int, str, float, str]]:
        normalized = str(text).replace("’", "'")
        matches: list[tuple[int, int, str, float, str]] = []
        for match in _COMMITMENT.finditer(normalized):
            matches.append((match.start("verb"), match.end("verb"), match.group("verb"), 0.96, "explicit commitment"))
        for match in _CHAINED.finditer(normalized):
            if any(start < match.start("verb") for start, *_ in matches):
                matches.append((match.start("verb"), match.end("verb"), match.group("verb"), 0.91, "chained action"))
        unique = {(start, end): (start, end, verb, score, reason) for start, end, verb, score, reason in matches}
        return sorted(unique.values(), key=lambda item: item[0])

    def parse(
        self,
        text: str,
        *,
        source_role: str = "assistant",
        apply_limit: bool = True,
    ) -> tuple[tuple[AbilityRequest, ...], tuple[SuppressedRequest, ...]]:
        if source_role.casefold() != "assistant":
            return (), (SuppressedRequest(str(text), "only assistant output is eligible"),)
        normalized = str(text).replace("’", "'")
        matches = self._matches(normalized)
        if not matches:
            return (), ()

        drafts: list[ActivationDraft] = []
        suppressed: list[SuppressedRequest] = []
        for index, (start, end, raw_verb, confidence, reason) in enumerate(matches):
            next_start = matches[index + 1][0] if index + 1 < len(matches) else len(normalized)
            full_tail = normalized[end:next_start]
            tail = full_tail
            tail = re.split(r"[!?\n]", tail, maxsplit=1)[0]
            tail = re.split(r"\.(?=\s+[A-Z]|\s*$)", tail, maxsplit=1)[0]
            tail = re.sub(r"(?is)\b(?:and\s+then|then|and)\s*$", "", tail)
            verb = self._canonical_verb(raw_verb)
            ability = _ALIASES[verb]
            arguments = self._arguments(ability, verb, tail)
            if ability == AbilityId.RUN:
                fenced_command = self._fenced_command(full_tail)
                if fenced_command is not None:
                    arguments = {"command": fenced_command}
            phrase = self._clean_tail(normalized[start:next_start])
            if not arguments or not any(str(value).strip() for value in arguments.values()):
                suppressed.append(SuppressedRequest(phrase, "no usable target or command", ability, confidence))
                continue
            drafts.append(ActivationDraft(ability, phrase, verb, arguments, confidence, (reason, f"verb:{verb}")))

        selected = drafts[: self.maximum_abilities] if apply_limit else drafts
        if apply_limit:
            for item in drafts[self.maximum_abilities :]:
                suppressed.append(SuppressedRequest(item.phrase, "per-pulse ability limit reached", item.ability_id, item.confidence))
        requests = tuple(
            AbilityRequest(
                request_id=f"request:{uuid.uuid4().hex}",
                ability_id=item.ability_id,
                phrase=item.phrase,
                arguments=item.arguments,
                confidence=item.confidence,
                reasons=item.reasons,
            )
            for item in selected
        )
        return requests, tuple(suppressed)
