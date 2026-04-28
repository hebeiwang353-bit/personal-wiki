"""
对 ChromaDB 中所有 Embedding 做 K-Means 聚类，
每个簇取最靠近质心的 top-k 文档，作为"代表性样本"送给 Claude 分析。
"""

import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import normalize


def cluster_and_sample(
    paths: list[str],
    embeddings: list[list[float]],
    texts: list[str],
    n_clusters: int = 80,
    top_k_per_cluster: int = 2,
) -> list[dict]:
    """
    返回采样后的文档列表：[{"path": str, "text": str, "cluster": int}, ...]
    n_clusters 决定主题粒度，top_k_per_cluster 决定每个主题取几篇代表。
    """
    if len(paths) == 0:
        return []

    n_clusters = min(n_clusters, len(paths) // 2 + 1)
    X = normalize(np.array(embeddings, dtype="float32"))

    # MiniBatchKMeans 在大数据量下比标准 KMeans 快很多
    kmeans = MiniBatchKMeans(
        n_clusters=n_clusters,
        random_state=42,
        batch_size=min(1024, len(paths)),
        n_init=3,
        max_iter=100,
    )
    labels = kmeans.fit_predict(X)
    centers = kmeans.cluster_centers_  # shape: (n_clusters, dim)

    selected = []
    for cluster_id in range(n_clusters):
        indices = np.where(labels == cluster_id)[0]
        if len(indices) == 0:
            continue

        # 计算每个成员到质心的余弦距离，取最近的 top_k
        cluster_vecs = X[indices]
        center = centers[cluster_id]
        sims = cluster_vecs @ center  # 余弦相似度（已归一化）
        top_indices = np.argsort(-sims)[:top_k_per_cluster]

        for idx in top_indices:
            real_idx = indices[idx]
            selected.append({
                "path": paths[real_idx],
                "text": texts[real_idx],
                "cluster": cluster_id,
                "cluster_size": len(indices),
            })

    return selected


def estimate_clusters(total_docs: int) -> int:
    """根据文档总数自动推荐聚类数"""
    if total_docs < 50:
        return max(5, total_docs // 3)
    if total_docs < 500:
        return 50
    if total_docs < 5000:
        return 100
    return 150
