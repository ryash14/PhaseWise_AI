"""One question, one language model call, answered from the documents and nothing else."""

import re

from agentic.agents import call_language_model, parse_labelled_response
from config import config
from knowledge.standard_reading import read_connection_standard
from knowledge.vector_index import search_documents
from tools.retrieval_tools import read_documentation_to_provide, read_reviewer_checks

FIELD_LABELS = ["QUESTION TYPE", "APPLICATION", "ANSWER"]


def _bare(value):
    return re.sub(config.RESPONSE_DECORATION_EDGE_PATTERN, "", value.strip())


def _single_line(value, field):
    if "\n" in value.strip():
        raise ValueError(
            f"{config.AGENT_NAME_CONNECTION_ASSISTANT} wrote {field} over more than one line"
        )
    return value.strip()


def _offered_passages(collection, question_text, search_text):
    found = search_documents(collection, [question_text, search_text])
    offered = {}
    for passages in found:
        for passage in passages:
            known = offered.get(passage["chunk_id"])
            if known is None or passage["distance"] < known["distance"]:
                offered[passage["chunk_id"]] = passage
    return sorted(offered.values(), key=lambda passage: passage["distance"])


def _standards_text(collection, document_entries):
    blocks = []
    for technology, document_name in config.CONNECTION_STANDARD_DOCUMENTS.items():
        standard = read_connection_standard(technology, document_entries)
        lines = [
            f"{config.TECHNOLOGY_NAMES[technology]} ({technology}), from {document_name}:"
        ]
        lines.extend(
            f"- {requirement['requirement_name']}: {requirement['requirement_sentence']}"
            for requirement in standard["requirements"]
        )
        lines.append(
            "- Documentation to provide: " + read_documentation_to_provide(collection, technology)
        )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _guides_text(collection):
    return "\n".join(
        f"- {sentence_type}, from {document_name}: "
        + read_reviewer_checks(collection, sentence_type)
        for sentence_type, document_name in config.SENTENCE_TYPE_GUIDE_DOCUMENTS.items()
    )


def _canonical_reference(reference):
    match = re.match(config.APPLICATION_REFERENCE_PATTERN, reference.upper())
    if match is None:
        return reference
    return config.APPLICATION_REFERENCE_PREFIX + match.group(1).zfill(
        config.APPLICATION_REFERENCE_DIGITS
    )


def _reference_is_named(reference, texts):
    lowered = [text.lower() for text in texts]
    if re.fullmatch(config.CANONICAL_APPLICATION_REFERENCE_PATTERN, reference):
        if any(reference.lower() in text for text in lowered):
            return True
        number = str(int(reference[len(config.APPLICATION_REFERENCE_PREFIX):]))
        pattern = config.NUMBER_IN_TEXT_PATTERN.format(number=number)
        return any(re.search(pattern, text) for text in texts)
    return any(reference.lower() in text for text in lowered)


def _substation_and_technology(question_text, previous_question):
    substations = [
        found.upper() for found in re.findall(config.SUBSTATION_IN_TEXT_PATTERN, question_text)
    ]
    if not substations and previous_question:
        substations = [
            found.upper()
            for found in re.findall(config.SUBSTATION_IN_TEXT_PATTERN, previous_question)
        ]

    def technologies_in(text):
        return [
            technology
            for technology, pattern in config.CHAT_TECHNOLOGY_PATTERNS.items()
            if re.search(pattern, text.lower())
        ]

    technologies = technologies_in(question_text)
    if not technologies and previous_question:
        technologies = technologies_in(previous_question)
    substations = list(dict.fromkeys(substations))
    if len(substations) == 1 and len(technologies) == 1:
        return substations[0], technologies[0]
    return None, None


def answer_from_documents(collection, document_entries, question_text, conversation):
    """Classify the question and answer it from the documents, or refuse."""
    passages = _offered_passages(collection, question_text, conversation["search_text"])
    passage_text = "\n\n".join(
        f"[{passage['document_name']}, section {passage['section_number']}] "
        f"{passage['chunk_text']}"
        for passage in passages
    )
    types_text = "\n".join(f"- {question_type}" for question_type in config.CHAT_TYPE_OPTIONS)
    prompt = (
        f"You are the connection assistant of {config.ORGANISATION_NAME}. You answer questions "
        "from Merrowdale's own documents and from nothing else. You know nothing about any "
        "individual application or substation: questions about those are answered from the "
        "records by the service, not by you.\n\n"
        f"QUESTION TYPES\n{types_text}\n"
        f"- {config.CHAT_TYPE_CONNECTION_STANDARD}: what a technology's connection standard "
        "requires or asks for.\n"
        f"- {config.CHAT_TYPE_CONNECTION_RULES}: how the Connection Rules or the Low-Carbon "
        "Connections Policy work.\n"
        f"- {config.CHAT_TYPE_STATEMENT_GUIDANCE}: what the statement guides say.\n"
        f"- {config.CHAT_TYPE_APPLICATION_STATUS}: the status of a named application.\n"
        f"- {config.CHAT_TYPE_OUTCOME_PREDICTION}: whether an application will need network "
        "work or how long it will take.\n"
        f"- {config.CHAT_TYPE_SUBSTATION_FIGURE}: how many of a technology are connected at a "
        "substation.\n"
        f"- {config.CHAT_TYPE_OUT_OF_SCOPE}: anything the documents do not cover.\n\n"
        "Keep each requirement to its own technology's standard.\n\n"
        f"CONVERSATION SO FAR\n{conversation['history_text']}\n\n"
        f"PASSAGES FOUND\n{passage_text or config.CHAT_NO_VALUE_REPLY}\n\n"
        f"WHAT EACH CONNECTION STANDARD REQUIRES\n{_standards_text(collection, document_entries)}\n\n"
        f"WHAT EACH STATEMENT GUIDE SAYS THE REVIEWER CHECKS\n{_guides_text(collection)}\n\n"
        f"QUESTION\n{question_text}\n\n"
        "Reply with exactly these labelled fields, each label at the start of its own line "
        f"followed by a colon. Write {config.CHAT_NO_VALUE_REPLY} in a field that does not apply.\n"
        "QUESTION TYPE: <one of the question types, on one line>\n"
        "APPLICATION: <the application reference the question is about, or "
        f"{config.CHAT_NO_VALUE_REPLY}, on one line>\n"
        "ANSWER: <the answer, from the documents only>"
    )
    reply = call_language_model(prompt, config.AGENT_NAME_CONNECTION_ASSISTANT)
    agent_name = config.AGENT_NAME_CONNECTION_ASSISTANT
    fields = parse_labelled_response(reply["response_text"], FIELD_LABELS, agent_name)
    question_type = _bare(_single_line(fields["QUESTION TYPE"], "QUESTION TYPE")).upper()
    application_field = _bare(_single_line(fields["APPLICATION"], "APPLICATION"))
    if question_type not in config.CHAT_TYPE_OPTIONS:
        raise ValueError(f"{agent_name} gave the question type {question_type}, which is unknown")
    if not application_field:
        raise ValueError(f"{agent_name} left APPLICATION empty")
    answer_text = fields["ANSWER"].strip()

    if question_type in config.CHAT_ANSWERED_TYPES:
        if re.search(config.APPLICATION_REFERENCE_IN_TEXT_PATTERN, question_text):
            question_type = config.CHAT_TYPE_APPLICATION_STATUS
        elif re.search(config.SUBSTATION_IN_TEXT_PATTERN, question_text):
            question_type = config.CHAT_TYPE_SUBSTATION_FIGURE

    closest_distance = passages[0]["distance"] if passages else None
    answered = (
        question_type in config.CHAT_ANSWERED_TYPES
        and closest_distance is not None
        and closest_distance <= config.CHAT_MAX_RELEVANCE_DISTANCE
    )
    if answered and _bare(answer_text).lower() == config.CHAT_NO_VALUE_REPLY.lower():
        raise ValueError(f"{agent_name} answered {config.CHAT_NO_VALUE_REPLY} to an answerable question")

    application_reference = None
    if question_type in config.CHAT_APPLICATION_TYPES:
        named = re.findall(config.APPLICATION_REFERENCE_IN_TEXT_PATTERN, question_text)
        if named:
            candidate = named[0]
        elif application_field.lower() != config.CHAT_NO_VALUE_REPLY.lower():
            candidate = application_field
        else:
            candidate = None
        if candidate is not None:
            application_reference = _canonical_reference(candidate)
            if not _reference_is_named(
                application_reference, [question_text, conversation["history_text"]]
            ):
                raise ValueError(
                    f"{agent_name} named the application {application_reference}, which neither "
                    "the question nor the conversation names"
                )

    substation_reference, technology = None, None
    if question_type == config.CHAT_TYPE_SUBSTATION_FIGURE:
        substation_reference, technology = _substation_and_technology(
            question_text, conversation["previous_question"]
        )

    source_documents = []
    was_refused = False
    if answered:
        if question_type == config.CHAT_TYPE_CONNECTION_STANDARD:
            source_documents.extend(config.CONNECTION_STANDARD_DOCUMENTS.values())
        if question_type == config.CHAT_TYPE_STATEMENT_GUIDANCE:
            source_documents.extend(config.SENTENCE_TYPE_GUIDE_DOCUMENTS.values())
        source_documents.extend(passage["document_name"] for passage in passages)
        source_documents = list(dict.fromkeys(source_documents))
    elif question_type not in config.CHAT_RECORD_TYPES:
        question_type = config.CHAT_TYPE_OUT_OF_SCOPE
        answer_text = config.CHAT_REFUSAL_MESSAGE
        was_refused = True

    return {
        "question_type": question_type,
        "application_reference": application_reference,
        "substation_reference": substation_reference,
        "technology": technology,
        "answer": answer_text,
        "source_documents": source_documents,
        "closest_distance": closest_distance,
        "was_refused": was_refused,
    }
