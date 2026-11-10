"""The four section reads the workflow and the chat need, each from one document alone."""

from config import config
from knowledge.vector_index import read_document_section


def _read_titled_section(collection, document_name, section_number, section_title):
    section_text = read_document_section(collection, document_name, section_number)
    heading = f"{section_number}. {section_title} "
    if not section_text.startswith(heading):
        raise ValueError(
            config.SECTION_TITLE_MISMATCH_MESSAGE.format(
                section_number=section_number,
                document_name=document_name,
                section_title=section_title,
            )
        )
    return section_text[len(heading):]


def _standard_document(technology):
    if technology not in config.CONNECTION_STANDARD_DOCUMENTS:
        raise ValueError(config.NO_STANDARD_CONFIGURED_MESSAGE.format(technology=technology))
    return config.CONNECTION_STANDARD_DOCUMENTS[technology]


def read_reviewer_checks(collection, sentence_type):
    """What a sentence type's statement guide says the reviewer checks."""
    if sentence_type not in config.SENTENCE_TYPE_GUIDE_DOCUMENTS:
        raise ValueError(config.NO_GUIDE_CONFIGURED_MESSAGE.format(sentence_type=sentence_type))
    return _read_titled_section(
        collection,
        config.SENTENCE_TYPE_GUIDE_DOCUMENTS[sentence_type],
        config.REVIEWER_CHECKS_SECTION_NUMBER,
        config.REVIEWER_CHECKS_SECTION_TITLE,
    )


def read_documentation_to_provide(collection, technology):
    """What a technology's own standard asks the installer to provide."""
    return _read_titled_section(
        collection,
        _standard_document(technology),
        config.DOCUMENTATION_SECTION_NUMBER,
        config.DOCUMENTATION_SECTION_TITLE,
    )


def read_connection_approval_guidance(collection, technology):
    """What a technology's own standard says the connection approval holds."""
    return _read_titled_section(
        collection,
        _standard_document(technology),
        config.CONNECTION_APPROVAL_SECTION_NUMBER,
        config.CONNECTION_APPROVAL_SECTION_TITLE,
    )


def read_household_notice_guidance(collection, technology):
    """What a technology's own standard says the household notice tells."""
    return _read_titled_section(
        collection,
        _standard_document(technology),
        config.HOUSEHOLD_NOTICE_SECTION_NUMBER,
        config.HOUSEHOLD_NOTICE_SECTION_TITLE,
    )
