"""Embeds, stores, reads back and searches the passages. The only module that talks to the store."""

import os

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from config import config

ADD_BATCH_SIZE = 256
SEARCH_BREADTH = 2000


def _embedding_function():
    """The embedding the store is built and searched with."""
    return SentenceTransformerEmbeddingFunction(
        model_name=config.EMBEDDING_MODEL_NAME, device=config.EMBEDDING_DEVICE
    )


def _collection_metadata():
    # A search breadth far above the passage count makes every search weigh every passage.
    return {
        "hnsw:space": config.VECTOR_DISTANCE_METRIC,
        "hnsw:search_ef": SEARCH_BREADTH,
        "hnsw:construction_ef": SEARCH_BREADTH,
    }


def build_vector_index(chunk_records, store_path):
    """Build (or replace) the persistent, searchable store of passages."""
    if os.path.isfile(store_path):
        raise ValueError(f"{store_path} is a file, where the store is kept in a folder")
    if os.path.isdir(store_path):
        held = os.listdir(store_path)
        if held and config.VECTOR_STORE_FILE_NAME not in held:
            raise ValueError(
                f"{store_path} holds files but no {config.VECTOR_STORE_FILE_NAME}, so it is not "
                "a store this project built"
            )
    embedding_function = _embedding_function()
    embedding_function(["The embedding model is ready."])
    os.makedirs(store_path, exist_ok=True)
    client = chromadb.PersistentClient(path=store_path)
    existing = [
        getattr(collection, "name", collection) for collection in client.list_collections()
    ]
    if config.VECTOR_COLLECTION_NAME in existing:
        client.delete_collection(config.VECTOR_COLLECTION_NAME)
    collection = client.create_collection(
        name=config.VECTOR_COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata=_collection_metadata(),
    )
    for start in range(0, len(chunk_records), ADD_BATCH_SIZE):
        batch = chunk_records[start:start + ADD_BATCH_SIZE]
        collection.add(
            ids=[record["chunk_id"] for record in batch],
            documents=[record["chunk_text"] for record in batch],
            metadatas=[
                {
                    "document_name": record["document_name"],
                    "section_number": int(record["section_number"]),
                    "passage_number": int(record["passage_number"]),
                    "carried_characters": int(record["carried_characters"]),
                }
                for record in batch
            ],
        )
    return collection.count()


def open_vector_index(store_path):
    """Open the store for reading and searching, without changing it."""
    if not os.path.isfile(os.path.join(store_path, config.VECTOR_STORE_FILE_NAME)):
        raise ValueError(
            f"{store_path} holds no {config.VECTOR_STORE_FILE_NAME}; run run_knowledge_indexing.py"
        )
    client = chromadb.PersistentClient(path=store_path)
    existing = [
        getattr(collection, "name", collection) for collection in client.list_collections()
    ]
    if config.VECTOR_COLLECTION_NAME not in existing:
        raise ValueError(
            f"The store at {store_path} holds no collection {config.VECTOR_COLLECTION_NAME}"
        )
    return client.get_collection(
        name=config.VECTOR_COLLECTION_NAME, embedding_function=_embedding_function()
    )


def read_document_section(collection, document_name, section_number):
    """Read one section of one document back, whole, exactly as it was divided."""
    stored = collection.get(
        where={
            "$and": [
                {"document_name": {"$eq": document_name}},
                {"section_number": {"$eq": int(section_number)}},
            ]
        },
        include=["documents", "metadatas"],
    )
    if not stored["ids"]:
        raise ValueError(
            config.NO_SECTION_PASSAGES_MESSAGE.format(
                section_number=section_number, document_name=document_name
            )
        )
    passages = sorted(
        zip(stored["documents"], stored["metadatas"]),
        key=lambda pair: int(pair[1]["passage_number"]),
    )
    section_text = passages[0][0]
    for text, metadata in passages[1:]:
        section_text += " " + text[int(metadata["carried_characters"]):]
    return section_text


def search_documents(collection, query_texts):
    """The nearest passages to each question, nearest first, never from the casebook."""
    results = collection.query(
        query_texts=list(query_texts),
        n_results=config.CHAT_RETRIEVAL_RESULT_COUNT,
        where={"document_name": {"$nin": list(config.CHAT_EXCLUDED_DOCUMENTS)}},
        include=["documents", "metadatas", "distances"],
    )
    answered = []
    for position in range(len(query_texts)):
        passages = []
        for chunk_id, text, metadata, distance in zip(
            results["ids"][position],
            results["documents"][position],
            results["metadatas"][position],
            results["distances"][position],
        ):
            passages.append(
                {
                    "chunk_id": chunk_id,
                    "chunk_text": text,
                    "document_name": metadata["document_name"],
                    "section_number": int(metadata["section_number"]),
                    "distance": float(distance),
                }
            )
        passages.sort(key=lambda passage: passage["distance"])
        answered.append(passages)
    return answered
