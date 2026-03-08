"""轻量级专利向量存储 - 无外部依赖"""
from __future__ import annotations
import json
import asyncio
from pathlib import Path
from dataclasses import dataclass, asdict
import numpy as np
from .fingerprint import PatentFingerprint


@dataclass
class SearchResult:
    patent_id: str
    score: float
    dimension: str = "composite"


class PatentVectorStore:
    """基于文件的专利指纹向量存储"""

    def __init__(self, storage_path: str):
        self._path = Path(storage_path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._fingerprints: dict[str, PatentFingerprint] = {}
        self._lock = asyncio.Lock()
        self._index_file = self._path / "index.json"
        self._load_index()

    def _load_index(self):
        if self._index_file.exists():
            try:
                data = json.loads(self._index_file.read_text(encoding="utf-8"))
                for pid, fp_data in data.items():
                    self._fingerprints[pid] = PatentFingerprint(**fp_data)
            except Exception:
                self._fingerprints = {}

    def _save_index(self):
        data = {}
        for pid, fp in self._fingerprints.items():
            d = {
                "patent_id": fp.patent_id,
                "structural_vector": fp.structural_vector,
                "technical_vector": fp.technical_vector,
                "legal_vector": fp.legal_vector,
                "semantic_vector": fp.semantic_vector,
                "innovation_vector": fp.innovation_vector,
                "composite_hash": fp.composite_hash,
                "claim_tree": fp.claim_tree,
                "technical_features": fp.technical_features,
                "keywords": fp.keywords,
                "metadata": fp.metadata,
                "version": fp.version,
            }
            data[pid] = d
        self._index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def add_fingerprint(self, fp: PatentFingerprint):
        async with self._lock:
            self._fingerprints[fp.patent_id] = fp
            self._save_index()

    async def get_fingerprint(self, patent_id: str) -> PatentFingerprint | None:
        return self._fingerprints.get(patent_id)

    async def delete_fingerprint(self, patent_id: str) -> bool:
        async with self._lock:
            if patent_id in self._fingerprints:
                del self._fingerprints[patent_id]
                self._save_index()
                return True
            return False

    async def search_by_vector(
        self, vector: list[float], dimension: str = "composite", top_k: int = 10, threshold: float = 0.3,
    ) -> list[SearchResult]:
        va = np.array(vector)
        na = np.linalg.norm(va)
        if na == 0:
            return []

        results = []
        for pid, fp in self._fingerprints.items():
            if dimension == "structural":
                vb = np.array(fp.structural_vector)
            elif dimension == "technical":
                vb = np.array(fp.technical_vector)
            elif dimension == "semantic":
                vb = np.array(fp.semantic_vector)
            else:
                vb = fp.to_composite_vector()

            nb = np.linalg.norm(vb)
            if nb == 0:
                continue
            score = float(np.dot(va, vb) / (na * nb))
            if score >= threshold:
                results.append(SearchResult(patent_id=pid, score=round(score, 4), dimension=dimension))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def search_by_keywords(self, keywords: list[str], top_k: int = 10) -> list[SearchResult]:
        kw_set = set(keywords)
        results = []
        for pid, fp in self._fingerprints.items():
            overlap = len(kw_set & set(fp.keywords))
            if overlap > 0:
                score = overlap / max(len(kw_set), 1)
                results.append(SearchResult(patent_id=pid, score=round(score, 4), dimension="keyword"))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def get_all_fingerprints(self) -> list[PatentFingerprint]:
        return list(self._fingerprints.values())

    def get_statistics(self) -> dict:
        return {"total_count": len(self._fingerprints), "storage_path": str(self._path)}
