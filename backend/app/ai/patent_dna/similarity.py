"""专利相似性计算引擎"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from .fingerprint import PatentFingerprint


@dataclass
class SimilarityResult:
    patent_id_1: str = ""
    patent_id_2: str = ""
    overall_score: float = 0.0
    structural_sim: float = 0.0
    technical_sim: float = 0.0
    legal_sim: float = 0.0
    semantic_sim: float = 0.0
    innovation_sim: float = 0.0
    overlapping_features: list[str] = field(default_factory=list)
    distinguishing_features: list[str] = field(default_factory=list)
    assessment: str = ""


@dataclass
class NoveltyScore:
    score: float = 0.0
    level: str = ""        # high / moderate / low
    most_similar_id: str = ""
    most_similar_score: float = 0.0
    novel_features: list[str] = field(default_factory=list)
    covered_features: list[str] = field(default_factory=list)
    assessment: str = ""


def _cosine_sim(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


class PatentSimilarityEngine:
    """多维度专利相似性计算"""

    # 各维度权重
    WEIGHTS = {"structural": 0.15, "technical": 0.30, "legal": 0.20, "semantic": 0.25, "innovation": 0.10}

    def compute_similarity(self, fp1: PatentFingerprint, fp2: PatentFingerprint) -> SimilarityResult:
        s_sim = _cosine_sim(fp1.structural_vector, fp2.structural_vector)
        t_sim = _cosine_sim(fp1.technical_vector, fp2.technical_vector)
        l_sim = _cosine_sim(fp1.legal_vector, fp2.legal_vector)
        se_sim = _cosine_sim(fp1.semantic_vector, fp2.semantic_vector)
        i_sim = _cosine_sim(fp1.innovation_vector, fp2.innovation_vector)

        overall = (self.WEIGHTS["structural"] * s_sim + self.WEIGHTS["technical"] * t_sim +
                   self.WEIGHTS["legal"] * l_sim + self.WEIGHTS["semantic"] * se_sim +
                   self.WEIGHTS["innovation"] * i_sim)

        # 特征重叠分析
        kw1 = set(fp1.keywords)
        kw2 = set(fp2.keywords)
        overlapping = list(kw1 & kw2)
        distinguishing = list(kw1 - kw2)

        # 评估
        if overall > 0.85:
            assessment = "高度相似 - 可能构成新颖性问题"
        elif overall > 0.65:
            assessment = "中度相似 - 需要详细比对技术特征"
        elif overall > 0.4:
            assessment = "低度相似 - 存在部分技术重叠"
        else:
            assessment = "差异显著 - 技术方案基本不同"

        return SimilarityResult(
            patent_id_1=fp1.patent_id, patent_id_2=fp2.patent_id,
            overall_score=round(overall, 4),
            structural_sim=round(s_sim, 4), technical_sim=round(t_sim, 4),
            legal_sim=round(l_sim, 4), semantic_sim=round(se_sim, 4),
            innovation_sim=round(i_sim, 4),
            overlapping_features=overlapping[:20],
            distinguishing_features=distinguishing[:20],
            assessment=assessment,
        )

    def find_similar_patents(
        self, fingerprint: PatentFingerprint, candidates: list[PatentFingerprint],
        top_k: int = 10, threshold: float = 0.4,
    ) -> list[SimilarityResult]:
        results = []
        for cand in candidates:
            if cand.patent_id == fingerprint.patent_id:
                continue
            sim = self.compute_similarity(fingerprint, cand)
            if sim.overall_score >= threshold:
                results.append(sim)
        results.sort(key=lambda r: r.overall_score, reverse=True)
        return results[:top_k]

    def compute_novelty_score(
        self, patent_fp: PatentFingerprint, prior_art_fps: list[PatentFingerprint],
    ) -> NoveltyScore:
        if not prior_art_fps:
            return NoveltyScore(score=95.0, level="high", assessment="无已知对比文件，新颖性评分较高")

        max_sim = 0.0
        most_similar_id = ""
        all_covered = set()
        for pa in prior_art_fps:
            sim = self.compute_similarity(patent_fp, pa)
            if sim.overall_score > max_sim:
                max_sim = sim.overall_score
                most_similar_id = pa.patent_id
            all_covered.update(sim.overlapping_features)

        novelty = max(0, (1.0 - max_sim) * 100)
        novel_features = [k for k in patent_fp.keywords if k not in all_covered]

        if novelty > 80:
            level, assessment = "high", "新颖性较强，与现有技术差异显著"
        elif novelty > 50:
            level, assessment = "moderate", "新颖性中等，部分技术特征与现有技术重叠"
        else:
            level, assessment = "low", "新颖性较弱，与现有技术高度相似"

        return NoveltyScore(
            score=round(novelty, 2), level=level,
            most_similar_id=most_similar_id, most_similar_score=round(max_sim, 4),
            novel_features=novel_features[:20],
            covered_features=list(all_covered)[:20],
            assessment=assessment,
        )
