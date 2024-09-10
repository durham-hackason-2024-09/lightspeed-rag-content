"""Utility script to generate embeddings."""

import argparse
import json
import os
import time
from typing import Callable, Dict

import faiss
import requests
from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.llms.utils import resolve_llm

# from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.schema import TextNode
from llama_index.core.storage.storage_context import StorageContext
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.faiss import FaissVectorStore

AAP_DOCS_VERSION = "2.5"
UNREACHABLE_DOCS: int = 0


def ping_url(url: str) -> bool:
    """Check if the URL parameter is live."""
    try:
        response = requests.get(url, timeout=30)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def get_file_title(file_path: str) -> str:
    """Extract title from the plaintext doc file."""
    title = ""
    try:
        with open(file_path, "r") as file:
            title = file.readline().rstrip("\n").lstrip("# ")
    except Exception:  # noqa: S110
        pass
    return title


def got_whitespace(text: str) -> bool:
    """Indicate if the parameter string contains whitespace."""
    for c in text:
        if c.isspace():
            return True
    return False


if __name__ == "__main__":

    start_time = time.time()

    parser = argparse.ArgumentParser(description="embedding cli for task execution")
    parser.add_argument("-f", "--folder", help="Plain text folder path")
    parser.add_argument(
        "-md",
        "--model-dir",
        default="embeddings_model",
        help="Directory containing the embedding model",
    )
    parser.add_argument(
        "-mn",
        "--model-name",
        help="HF repo id of the embedding model",
    )
    parser.add_argument(
        "-c", "--chunk", type=int, default=380, help="Chunk size for embedding"
    )
    parser.add_argument(
        "-l", "--overlap", type=int, default=0, help="Chunk overlap for embedding"
    )
    parser.add_argument(
        "-em",
        "--exclude-metadata",
        nargs="+",
        default=None,
        help="Metadata to be excluded during embedding",
    )
    parser.add_argument("-o", "--output", help="Vector DB output folder")
    parser.add_argument("-i", "--index", help="Product index")
    parser.add_argument("-v", "--aap-version", help="AAP version")
    args = parser.parse_args()
    print(f"Arguments used: {args}")

    # OLS-823: sanitize directory
    PERSIST_FOLDER = os.path.normpath("/" + args.output).lstrip("/")
    if PERSIST_FOLDER == "":
        PERSIST_FOLDER = "."

    EMBEDDINGS_ROOT_DIR = os.path.abspath(args.folder)
    if EMBEDDINGS_ROOT_DIR.endswith("/"):
        EMBEDDINGS_ROOT_DIR = EMBEDDINGS_ROOT_DIR[:-1]

    AAP_DOCS_VERSION = args.aap_version

    os.environ["HF_HOME"] = args.model_dir
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    Settings.chunk_size = args.chunk
    Settings.chunk_overlap = args.overlap
    Settings.embed_model = HuggingFaceEmbedding(model_name=args.model_dir)
    Settings.llm = resolve_llm(None)

    embedding_dimension = len(Settings.embed_model.get_text_embedding("random text"))
    faiss_index = faiss.IndexFlatIP(embedding_dimension)
    vector_store = FaissVectorStore(faiss_index=faiss_index)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Load documents
    documents = SimpleDirectoryReader(
        args.folder, recursive=True
    ).load_data()

    # Split based on header/section
    # md_parser = MarkdownNodeParser()
    # documents = md_parser.get_nodes_from_documents(documents)

    # Create chunks/nodes
    nodes = Settings.text_splitter.get_nodes_from_documents(documents)

    # Filter out invalid nodes
    good_nodes = []
    for node in nodes:
        if isinstance(node, TextNode) and got_whitespace(node.text):
            # Exclude given metadata during embedding
            # if args.exclude_metadata is not None:
            #     node.excluded_embed_metadata_keys.extend(args.exclude_metadata)
            good_nodes.append(node)
        else:
            print("skipping node without whitespace: " + node.__repr__())

    # Create & save Index
    index = VectorStoreIndex(
        good_nodes,
        storage_context=storage_context,
    )
    index.set_index_id(args.index)
    index.storage_context.persist(persist_dir=PERSIST_FOLDER)

    metadata: dict = {}
    metadata["execution-time"] = time.time() - start_time
    metadata["llm"] = "None"
    metadata["embedding-model"] = args.model_name
    metadata["index-id"] = args.index
    metadata["vector-db"] = "faiss.IndexFlatIP"
    metadata["embedding-dimension"] = embedding_dimension
    metadata["chunk"] = args.chunk
    metadata["overlap"] = args.overlap
    metadata["total-embedded-files"] = len(documents)

    with open(os.path.join(PERSIST_FOLDER, "metadata.json"), "w") as file:
        file.write(json.dumps(metadata))

    if UNREACHABLE_DOCS > 0:
        print("WARNING:\n"
            f"There were documents with {UNREACHABLE_DOCS} unreachable URLs, "
            "grep the log for UNREACHABLE.\n"
            "Please update the plain text."
        )
