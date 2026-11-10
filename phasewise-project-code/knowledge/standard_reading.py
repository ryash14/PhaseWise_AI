"""Reads a technology's requirements out of that technology's own connection standard.

No requirement and no figure is written into the code: everything comes from
section 4 of the standard's own document, read at run time.
"""

import re
from decimal import Decimal

from config import config
from knowledge.chunk_splitting import split_documents_into_sections

FIGURE_PARTS = [
    config.MAXIMUM_AMPS_RULE,
    config.MINIMUM_POWER_FACTOR_RULE,
    config.MAXIMUM_OHMS_RULE,
]


def _own_document(technology, document_entries):
    document_name = config.CONNECTION_STANDARD_DOCUMENTS[technology]
    matching = [entry for entry in document_entries if entry["document_name"] == document_name]
    if len(matching) != 1:
        raise ValueError(
            f"{document_name} appears {len(matching)} times among the documents read, "
            "where the standard is read from exactly one"
        )
    return document_name, matching[0]


def _section(sections, number, document_name):
    found = [section for section in sections if section["section_number"] == number]
    if len(found) != 1:
        raise ValueError(f"{document_name} has no section {number} to read the standard from")
    return found[0]["section_text"]


def _read_requirement(piece, document_name):
    fitting = []
    for kind, pattern in config.REQUIREMENT_SENTENCE_PATTERNS.items():
        match = re.fullmatch(pattern, piece)
        if match is not None:
            fitting.append((kind, match))
    if len(fitting) != 1:
        raise ValueError(
            f"{document_name} states a requirement no single form of the Connection Rules "
            f"reads: {piece}"
        )
    kind, match = fitting[0]
    parts = match.groupdict()
    rules = {
        part: Decimal(parts[part]) for part in FIGURE_PARTS if parts.get(part) is not None
    }
    return {
        "requirement_kind": kind,
        "requirement_name": parts[config.REQUIREMENT_NAME_PART],
        "requirement_sentence": parts[config.REQUIREMENT_SENTENCE_PART],
        "rules": rules,
    }


def read_connection_standard(technology, document_entries):
    """Every requirement of one technology, with its own figures, from its own standard."""
    if technology not in config.CONNECTION_STANDARD_DOCUMENTS:
        raise ValueError(config.NO_STANDARD_CONFIGURED_MESSAGE.format(technology=technology))
    document_name, entry = _own_document(technology, document_entries)
    sections = split_documents_into_sections([entry])

    technology_text = _section(sections, config.TECHNOLOGY_SECTION_NUMBER, document_name)
    codes = re.findall(config.TECHNOLOGY_CODE_PATTERN, technology_text)
    if codes != [technology]:
        raise ValueError(
            f"{document_name} states the technology codes {codes} in section "
            f"{config.TECHNOLOGY_SECTION_NUMBER}, where it states {technology} once and no other"
        )

    requirements_text = _section(sections, config.REQUIREMENTS_SECTION_NUMBER, document_name)
    whole = re.fullmatch(config.REQUIREMENTS_SECTION_PATTERN, requirements_text)
    if whole is None:
        raise ValueError(
            f"Section {config.REQUIREMENTS_SECTION_NUMBER} of {document_name} is not laid out "
            "as the requirements of a connection standard"
        )
    pieces = re.split(config.REQUIREMENT_NUMBER_PATTERN, whole.group(1))
    if pieces[0].strip():
        raise ValueError(f"{document_name} has text before its first requirement")
    numbers = [int(number) for number in pieces[1::2]]
    if not numbers or numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(
            f"{document_name} numbers its requirements {numbers}, where they run from 1 in order"
        )
    requirements = []
    seen_kinds = set()
    for piece in pieces[2::2]:
        requirement = _read_requirement(piece.strip(), document_name)
        if requirement["requirement_kind"] in seen_kinds:
            raise ValueError(
                f"{document_name} states the requirement kind "
                f"{requirement['requirement_kind']} twice"
            )
        seen_kinds.add(requirement["requirement_kind"])
        requirements.append(requirement)
    return {
        "technology": technology,
        "document_name": document_name,
        "requirements": requirements,
    }
