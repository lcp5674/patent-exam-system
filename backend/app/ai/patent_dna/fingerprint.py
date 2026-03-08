"""
专利 DNA 指纹引擎 (Patent DNA Fingerprint Engine)
────────────────────────────────────────────────────
本系统核心技术壁垒：将每件专利抽象为多维度 "DNA 指纹"，
包括结构DNA、技术DNA、法律DNA、语义DNA、创新DNA五个维度，
实现深度结构比较、相似性检测和智能审查辅助。
"""
from __future__ import annotations
import hashlib
import re
import math
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

try:
    import jieba
    import jieba.analyse
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

PATENT_STOP_WORDS = {"的", "了", "在", "是", "和", "或", "与", "及", "其", "所述", "一种",
    "包括", "具有", "用于", "根据", "通过", "进行", "可以", "能够", "设置", "连接", "安装"}

STRUCTURAL_KEYWORDS = {"形状", "外形", "轮廓", "截面", "横截面", "几何", "弯曲", "弧形", "锥形"}
COMPOSITIONAL_KEYWORDS = {"构造", "结构", "组件", "零件", "部件", "装置", "机构", "连接", "固定", "卡扣"}
FUNCTIONAL_KEYWORDS = {"功能", "作用", "效果", "性能", "效率", "强度", "精度", "稳定", "可靠"}


@dataclass
class TechnicalFeature:
    name: str
    category: str = "general"      # structural / compositional / functional / general
    weight: float = 1.0
    position: str = "description"  # claims / abstract / description
    relationships: list[str] = field(default_factory=list)


@dataclass
class ClaimTree:
    root_claims: list[int] = field(default_factory=list)
    tree_structure: dict = field(default_factory=dict)
    depth: int = 0
    width: int = 0
    features_by_level: dict = field(default_factory=dict)
    total_claims: int = 0


@dataclass
class InnovationDelta:
    distinguishing_features: list[str] = field(default_factory=list)
    innovation_type: str = ""           # shape / structure / combination / application
    magnitude: float = 0.0             # 0-1
    summary: str = ""


@dataclass
class PatentFingerprint:
    patent_id: str = ""
    # 五维向量 (各64维)
    structural_vector: list[float] = field(default_factory=lambda: [0.0]*64)
    technical_vector: list[float] = field(default_factory=lambda: [0.0]*64)
    legal_vector: list[float] = field(default_factory=lambda: [0.0]*64)
    semantic_vector: list[float] = field(default_factory=lambda: [0.0]*64)
    innovation_vector: list[float] = field(default_factory=lambda: [0.0]*64)
    # 复合哈希 (用于快速去重)
    composite_hash: str = ""
    # 结构化元数据
    claim_tree: dict = field(default_factory=dict)
    technical_features: list[dict] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    version: str = "1.0"

    def to_composite_vector(self) -> np.ndarray:
        """合成 320 维复合向量"""
        return np.concatenate([
            self.structural_vector, self.technical_vector,
            self.legal_vector, self.semantic_vector, self.innovation_vector
        ])


class PatentDNAEngine:
    """专利 DNA 指纹生成引擎"""

    VECTOR_DIM = 64   # 每个维度的向量长度

    def __init__(self):
        self._vocab: dict[str, int] = {}
        self._idf: dict[str, float] = {}

    # ─── 主入口 ──────────────────────────────────────────
    def generate_fingerprint(
        self,
        patent_id: str,
        claims_text: str = "",
        description_text: str = "",
        abstract_text: str = "",
        title: str = "",
    ) -> PatentFingerprint:
        """为一件专利生成完整的 DNA 指纹"""

        # 提取技术特征
        features = self.extract_technical_features(claims_text, description_text, abstract_text)
        keywords = [f.name for f in features[:50]]

        # 构建权利要求树
        claim_tree = self.build_claim_tree(claims_text)

        # 计算五维向量
        structural_vec = self._compute_structural_vector(claims_text, description_text, claim_tree)
        technical_vec = self._compute_technical_vector(features)
        legal_vec = self._compute_legal_vector(claims_text, claim_tree)
        semantic_vec = self._compute_semantic_vector(claims_text + " " + abstract_text, features)
        innovation_vec = self._compute_innovation_vector(features, claim_tree)

        # 复合哈希
        composite_hash = self._compute_composite_hash(
            structural_vec, technical_vec, legal_vec, semantic_vec, innovation_vec, title
        )

        return PatentFingerprint(
            patent_id=patent_id,
            structural_vector=structural_vec,
            technical_vector=technical_vec,
            legal_vector=legal_vec,
            semantic_vector=semantic_vec,
            innovation_vector=innovation_vec,
            composite_hash=composite_hash,
            claim_tree=claim_tree.__dict__ if isinstance(claim_tree, ClaimTree) else claim_tree,
            technical_features=[{"name": f.name, "category": f.category, "weight": f.weight} for f in features[:30]],
            keywords=keywords,
            metadata={"title": title, "claim_count": claim_tree.total_claims if isinstance(claim_tree, ClaimTree) else 0},
        )

    # ─── 技术特征提取 ────────────────────────────────────
    def extract_technical_features(
        self, claims: str = "", description: str = "", abstract: str = ""
    ) -> list[TechnicalFeature]:
        features: list[TechnicalFeature] = []
        # 从不同部分提取，权重不同 (权利要求 > 摘要 > 说明书)
        for text, pos, base_w in [(claims, "claims", 3.0), (abstract, "abstract", 2.0), (description, "description", 1.0)]:
            if not text:
                continue
            words = self._segment(text)
            seen = set()
            for w in words:
                if w in seen or len(w) < 2 or w in PATENT_STOP_WORDS:
                    continue
                seen.add(w)
                cat = self._classify_feature(w)
                features.append(TechnicalFeature(name=w, category=cat, weight=base_w, position=pos))

        # 按权重排序
        features.sort(key=lambda f: f.weight, reverse=True)
        return features

    # ─── 权利要求树 ──────────────────────────────────────
    def build_claim_tree(self, claims_text: str) -> ClaimTree:
        if not claims_text:
            return ClaimTree()

        tree = ClaimTree()
        # 拆分权利要求
        claim_pattern = re.compile(r'(?:权利要求|claim)\s*(\d+)', re.IGNORECASE)
        dep_pattern = re.compile(r'(?:根据|如)权利要求\s*(\d+)\s*所述', re.IGNORECASE)
        # 简单按编号拆分
        parts = re.split(r'\n\s*\d+[\.\、]', claims_text)
        tree.total_claims = max(len(parts) - 1, 1)

        # 识别独立/从属
        dependencies: dict[int, int] = {}
        for i, part in enumerate(parts):
            claim_num = i  # 简化处理
            dep_match = dep_pattern.search(part)
            if dep_match:
                parent = int(dep_match.group(1))
                dependencies[claim_num] = parent
            elif i > 0:
                tree.root_claims.append(claim_num)

        if not tree.root_claims and tree.total_claims > 0:
            tree.root_claims = [1]

        tree.tree_structure = dependencies
        tree.depth = self._calc_tree_depth(dependencies, tree.root_claims)
        tree.width = len(tree.root_claims)
        return tree

    # ─── 向量计算 ────────────────────────────────────────
    def _compute_structural_vector(self, claims: str, description: str, claim_tree) -> list[float]:
        """结构 DNA：文档结构模式"""
        vec = np.zeros(self.VECTOR_DIM, dtype=np.float64)
        # 结构特征
        vec[0] = min(len(claims) / 5000.0, 1.0)           # 权利要求长度归一化
        vec[1] = min(len(description) / 20000.0, 1.0)     # 说明书长度归一化
        ct = claim_tree if isinstance(claim_tree, ClaimTree) else ClaimTree()
        vec[2] = min(ct.total_claims / 20.0, 1.0)         # 权利要求数量
        vec[3] = min(ct.depth / 5.0, 1.0)                 # 树深度
        vec[4] = min(ct.width / 5.0, 1.0)                 # 独立权利要求数
        # 章节特征
        sections = ["技术领域", "背景技术", "发明内容", "附图说明", "具体实施方式"]
        for i, sec in enumerate(sections):
            vec[5+i] = 1.0 if sec in description else 0.0
        # 文本统计特征
        vec[10] = min(claims.count("其特征在于") / 10.0, 1.0)
        vec[11] = min(description.count("实施例") / 10.0, 1.0)
        # 用文本哈希填充剩余维度
        text_hash = hashlib.sha256((claims + description).encode()).digest()
        for i in range(12, self.VECTOR_DIM):
            vec[i] = text_hash[i % 32] / 255.0
        return vec.tolist()

    def _compute_technical_vector(self, features: list[TechnicalFeature]) -> list[float]:
        """技术 DNA：核心技术特征"""
        vec = np.zeros(self.VECTOR_DIM, dtype=np.float64)
        if not features:
            return vec.tolist()
        # 按类别统计
        cat_counts = {"structural": 0, "compositional": 0, "functional": 0, "general": 0}
        for f in features:
            cat_counts[f.category] = cat_counts.get(f.category, 0) + 1
        total = max(sum(cat_counts.values()), 1)
        vec[0] = cat_counts["structural"] / total
        vec[1] = cat_counts["compositional"] / total
        vec[2] = cat_counts["functional"] / total
        vec[3] = cat_counts["general"] / total
        vec[4] = min(len(features) / 100.0, 1.0)
        # 特征名哈希投影
        for i, f in enumerate(features[:self.VECTOR_DIM - 5]):
            h = int(hashlib.md5(f.name.encode()).hexdigest()[:8], 16)
            idx = 5 + (h % (self.VECTOR_DIM - 5))
            vec[idx] = min(vec[idx] + f.weight / 10.0, 1.0)
        # 归一化
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def _compute_legal_vector(self, claims: str, claim_tree) -> list[float]:
        """法律 DNA：权利要求范围模式"""
        vec = np.zeros(self.VECTOR_DIM, dtype=np.float64)
        ct = claim_tree if isinstance(claim_tree, ClaimTree) else ClaimTree()
        vec[0] = min(ct.total_claims / 20.0, 1.0)
        vec[1] = min(len(ct.root_claims) / 5.0, 1.0)
        vec[2] = min(ct.depth / 5.0, 1.0)
        # 法律术语密度
        legal_terms = ["其特征在于", "所述", "包括", "还包括", "进一步", "优选"]
        for i, term in enumerate(legal_terms):
            if i + 3 < self.VECTOR_DIM:
                vec[3+i] = min(claims.count(term) / 20.0, 1.0)
        # 哈希填充
        h = hashlib.sha256(claims.encode()).digest()
        for i in range(10, self.VECTOR_DIM):
            vec[i] = h[i % 32] / 255.0
        return vec.tolist()

    def _compute_semantic_vector(self, text: str, features: list[TechnicalFeature]) -> list[float]:
        """语义 DNA：基于 TF-IDF 的语义向量"""
        vec = np.zeros(self.VECTOR_DIM, dtype=np.float64)
        if not text:
            return vec.tolist()
        words = self._segment(text)
        word_counts: dict[str, int] = {}
        for w in words:
            if len(w) >= 2 and w not in PATENT_STOP_WORDS:
                word_counts[w] = word_counts.get(w, 0) + 1
        total_words = max(sum(word_counts.values()), 1)
        # 哈希投影到固定维度
        for word, count in word_counts.items():
            tf = count / total_words
            h = int(hashlib.md5(word.encode()).hexdigest()[:8], 16)
            idx = h % self.VECTOR_DIM
            vec[idx] += tf
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def _compute_innovation_vector(self, features: list[TechnicalFeature], claim_tree) -> list[float]:
        """创新 DNA：创新贡献指纹"""
        vec = np.zeros(self.VECTOR_DIM, dtype=np.float64)
        # 使用权利要求中的高权重特征
        claim_features = [f for f in features if f.position == "claims"]
        for i, f in enumerate(claim_features[:self.VECTOR_DIM]):
            h = int(hashlib.md5(f.name.encode()).hexdigest()[:8], 16)
            idx = h % self.VECTOR_DIM
            vec[idx] = min(vec[idx] + f.weight / 5.0, 1.0)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def _compute_composite_hash(self, *vectors_and_title) -> str:
        """计算复合哈希用于快速去重"""
        data = ""
        for v in vectors_and_title:
            if isinstance(v, list):
                data += "|".join(f"{x:.4f}" for x in v[:8])
            else:
                data += str(v)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    # ─── 辅助方法 ────────────────────────────────────────
    def _segment(self, text: str) -> list[str]:
        if HAS_JIEBA:
            return list(jieba.cut(text))
        # 降级：简单按标点和空格分词
        return re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]+', text)

    def _classify_feature(self, word: str) -> str:
        if word in STRUCTURAL_KEYWORDS or any(k in word for k in STRUCTURAL_KEYWORDS):
            return "structural"
        if word in COMPOSITIONAL_KEYWORDS or any(k in word for k in COMPOSITIONAL_KEYWORDS):
            return "compositional"
        if word in FUNCTIONAL_KEYWORDS or any(k in word for k in FUNCTIONAL_KEYWORDS):
            return "functional"
        return "general"

    def _calc_tree_depth(self, deps: dict, roots: list) -> int:
        if not deps:
            return 1
        max_depth = 1
        for node, parent in deps.items():
            depth = 1
            current = node
            visited = set()
            while current in deps and current not in visited:
                visited.add(current)
                current = deps[current]
                depth += 1
            max_depth = max(max_depth, depth)
        return max_depth

    def extract_innovation_delta(
        self, patent_features: list[TechnicalFeature], prior_art_keywords: list[str]
    ) -> InnovationDelta:
        """提取创新增量"""
        prior_set = set(prior_art_keywords)
        distinguishing = [f.name for f in patent_features if f.name not in prior_set]
        if not distinguishing:
            return InnovationDelta(magnitude=0.0, summary="未发现区别技术特征")
        magnitude = min(len(distinguishing) / max(len(patent_features), 1), 1.0)
        # 判断创新类型
        cats = [f.category for f in patent_features if f.name in distinguishing]
        if cats.count("structural") > len(cats) * 0.5:
            itype = "shape"
        elif cats.count("compositional") > len(cats) * 0.5:
            itype = "structure"
        else:
            itype = "combination"
        return InnovationDelta(
            distinguishing_features=distinguishing[:20],
            innovation_type=itype,
            magnitude=magnitude,
            summary=f"发现 {len(distinguishing)} 个区别技术特征，创新类型为{itype}"
        )
