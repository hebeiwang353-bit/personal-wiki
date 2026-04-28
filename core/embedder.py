"""
文本 Embedding + ChromaDB 持久化存储。
- Embedding 模型：OpenAI text-embedding-3-small（$0.02/百万token）
- 本地存储：./chroma_db/（增量更新，已存的文件不重复处理）
"""

import hashlib
import time
from pathlib import Path
from typing import Iterator

import chromadb
from openai import OpenAI

EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE = 50          # 每次 OpenAI API 调用的文本数
COLLECTION_NAME = "user_files"
DB_PATH = Path(__file__).parent / "chroma_db"

_chroma_client = None
_collection = None
_openai_client = None


def _get_collection() -> chromadb.Collection:
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=str(DB_PATH))
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI()
    return _openai_client


def _file_id(path: str) -> str:
    """用路径的 MD5 作为 ChromaDB 文档 ID"""
    return hashlib.md5(path.encode()).hexdigest()


def already_embedded(paths: list[str]) -> set[str]:
    """返回已经存在于 ChromaDB 中的路径集合（增量更新用）"""
    col = _get_collection()
    if col.count() == 0:
        return set()
    ids = [_file_id(p) for p in paths]
    result = col.get(ids=ids, include=[])
    existing_ids = set(result["ids"])
    return {p for p in paths if _file_id(p) in existing_ids}


def embed_and_store(items: list[dict], progress_cb=None) -> int:
    """
    items: [{"path": str, "text": str, "mtime": float, "size": int}, ...]
    返回实际新增的文档数。
    """
    col = _get_collection()
    client = _get_openai()

    # 过滤掉已存在的
    existing = already_embedded([i["path"] for i in items])
    new_items = [i for i in items if i["path"] not in existing]

    if not new_items:
        return 0

    added = 0
    for batch_start in range(0, len(new_items), BATCH_SIZE):
        batch = new_items[batch_start: batch_start + BATCH_SIZE]
        texts = [item["text"] for item in batch]

        # 调用 OpenAI Embedding
        try:
            resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
            embeddings = [d.embedding for d in resp.data]
        except Exception as e:
            print(f"  [Embedding 失败] {e}")
            time.sleep(2)
            continue

        # 存入 ChromaDB
        col.add(
            ids=[_file_id(item["path"]) for item in batch],
            embeddings=embeddings,
            documents=texts,
            metadatas=[
                {
                    "path": item["path"],
                    "mtime": item.get("mtime", 0),
                    "size": item.get("size", 0),
                }
                for item in batch
            ],
        )
        added += len(batch)
        if progress_cb:
            progress_cb(len(batch))
        time.sleep(0.1)  # 避免限流

    return added


def total_stored() -> int:
    return _get_collection().count()


def get_all_embeddings() -> tuple[list[str], list[list[float]], list[str]]:
    """
    返回 (paths, embeddings, texts) —— 用于聚类
    一次性拉取全部（适合 <10万 条）
    """
    col = _get_collection()
    count = col.count()
    if count == 0:
        return [], [], []

    result = col.get(include=["embeddings", "documents", "metadatas"], limit=count)
    paths = [m["path"] for m in result["metadatas"]]
    embeddings = result["embeddings"]
    texts = result["documents"]
    return paths, embeddings, texts
