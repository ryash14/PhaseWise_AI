"""Gets the text out of the PDFs and does nothing else with it."""

import os

from pypdf import PdfReader

from config import config


def extract_text_from_directory(docs_directory):
    """Read every PDF in a folder once, in name order, one page to a line break."""
    names = sorted(
        name
        for name in os.listdir(docs_directory)
        if name.lower().endswith(config.PDF_FILE_SUFFIX.lower())
        and os.path.isfile(os.path.join(docs_directory, name))
    )
    if not names:
        raise ValueError(f"The folder {docs_directory} holds no PDF document")
    documents = []
    for name in names:
        file_path = os.path.join(docs_directory, name)
        reader = PdfReader(file_path)
        if len(reader.pages) == 0:
            raise ValueError(f"{file_path} has no pages")
        page_texts = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                raise ValueError(f"Page {page_number} of {file_path} gives up no text")
            page_texts.append(text)
        documents.append({"document_name": name, "document_text": "\n".join(page_texts)})
    return documents
