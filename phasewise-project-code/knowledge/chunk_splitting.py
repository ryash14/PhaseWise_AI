"""Cuts the documents into numbered sections and overlapping passages of whole sentences."""

import re

from config import config


def _normalise(text):
    return re.sub(config.WHITESPACE_RUN_PATTERN, " ", text).strip()


def split_documents_into_sections(document_entries):
    """Divide each document at its numbered headings, below its one header line."""
    sections = []
    for entry in document_entries:
        document_name = entry["document_name"]
        text = entry["document_text"]
        headers = list(re.finditer(config.DOCUMENT_HEADER_PATTERN, text))
        if len(headers) != 1:
            raise ValueError(
                f"{document_name} carries {len(headers)} header lines where it carries one"
            )
        body = text[headers[0].end():]
        headings = list(re.finditer(config.SECTION_HEADING_PATTERN, body))
        numbers = [int(heading.group(1)) for heading in headings]
        if not numbers or numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(
                f"{document_name} has sections numbered {numbers} where they run from 1 in order"
            )
        for position, heading in enumerate(headings):
            end = headings[position + 1].start() if position + 1 < len(headings) else len(body)
            sections.append(
                {
                    "document_name": document_name,
                    "section_number": numbers[position],
                    "section_text": _normalise(body[heading.start():end]),
                }
            )
    return sections


def _joined_length(sentences):
    return len(" ".join(sentences))


def build_chunk_records(section_entries):
    """Cut each section into passages of whole sentences that overlap their neighbours."""
    records = []
    passage_numbers = {}
    for section in section_entries:
        document_name = section["document_name"]
        sentences = [
            sentence
            for sentence in re.split(config.SENTENCE_BOUNDARY_PATTERN, section["section_text"])
            if sentence
        ]
        if not sentences:
            sentences = [section["section_text"]]
        index = 0
        previous = None
        while index < len(sentences):
            carried = []
            if previous is not None:
                for sentence in reversed(previous):
                    candidate = [sentence] + carried
                    if _joined_length(candidate) <= config.CHUNK_OVERLAP_CHARACTERS:
                        carried = candidate
                    else:
                        break
                while carried and (
                    _joined_length(carried + [sentences[index]]) > config.CHUNK_SIZE_CHARACTERS
                ):
                    carried = carried[1:]
            current = carried + [sentences[index]]
            index += 1
            while index < len(sentences) and (
                _joined_length(current + [sentences[index]]) <= config.CHUNK_SIZE_CHARACTERS
            ):
                current.append(sentences[index])
                index += 1
            passage_number = passage_numbers.get(document_name, 0)
            passage_numbers[document_name] = passage_number + 1
            records.append(
                {
                    "chunk_id": f"{document_name}::passage-{passage_number:04d}",
                    "chunk_text": " ".join(current),
                    "document_name": document_name,
                    "section_number": int(section["section_number"]),
                    "passage_number": passage_number,
                    "carried_characters": _joined_length(carried) + 1 if carried else 0,
                }
            )
            previous = current
    return records
