# ============================================================================
#  rag.py —— 轻量 RAG 检索层(不依赖外部 embedding 服务)
#
#  为什么不用 Agnes embedding: Agnes 网关没暴露 embedding 接口(404), 本机也没装
#  sentence_transformers。所以这里用「纯本地 TF-IDF + 余弦」做向量检索 ——
#  它的好处:
#    1. 零外部依赖, 不受 Agnes 限流影响, 检索永远可复现(配合 mock 评测)
#    2. 面试可讲"检索层与 LLM 解耦": 换任何 embedding 模型/向量库都只改这一层
#  生产可平滑升级: 把 _vectorize 换成真实 embedding, 把内存索引换成
#  pgvector/Milvus, 检索接口 search() 不变。
#
#  面试重点(引用溯源): 每个 chunk 带 source/section, search() 返回"命中块 + 来源",
#  LLM 答案必须基于这些块, 标引用 —— 这就是 JD 里"RAG 全链路 + 引用溯源"。
# ============================================================================
import re
import math
import json
from collections import Counter

from app.agent.rag_data.knowledge import KNOWLEDGE

# 简单的中文/英文混合分词: 按 2-gram + 英文单词 + 数字切
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[一-鿿]{1,2}")


def _tokenize(text: str) -> list:
    """粗分词: 英文/数字整词, 中文按 2-gram(覆盖"剪辑/显卡/水冷"等双字词)。
    生产可换 jieba 分词 + 真实 embedding, 这里保持零依赖。"""
    toks = []
    for m in _TOKEN_RE.finditer(text):
        w = m.group(0)
        if re.fullmatch(r"[一-鿿]", w):
            continue  # 单字太碎, 跳过
        toks.append(w.lower())
    return toks


class LocalRetriever:
    """TF-IDF 余弦检索。一次 build, 多次 search。"""

    def __init__(self, chunks: list = None):
        self.chunks = chunks if chunks is not None else [
            {"text": k["text"], "source": k["source"], "section": k["section"]}
            for k in KNOWLEDGE
        ]
        self._vectors = [Counter(_tokenize(c["text"])) for c in self.chunks]
        # IDF: 词出现在多少 chunk 里(越少越有区分度)
        df = Counter()
        for v in self._vectors:
            for t in v:
                df[t] += 1
        self._n_docs = len(self.chunks)
        self._idf = {t: math.log(self._n_docs / (1 + c)) for t, c in df.items()}

    def _tfidf(self, counter: Counter) -> dict:
        raw = {t: c for t, c in counter.items()}
        return {t: (raw.get(t, 0) + 1) * self._idf.get(t, 0.0) for t in raw}

    def search(self, query: str, top_k: int = 3) -> list:
        """返回 top_k 个相关 chunk, 每个带 {text, source, section, score}。
        这是给 LLM 当工具用的"检索器", 上层把它当知识来源 + 引用。"""
        qv = self._tfidf(Counter(_tokenize(query)))
        scored = []
        for i, cv in enumerate(self._vectors):
            cvec = self._tfidf(cv)
            # 余弦相似度
            dot = sum(qv.get(t, 0) * cvec.get(t, 0) for t in qv)
            nq = math.sqrt(sum(x * x for x in qv.values())) or 1
            nc = math.sqrt(sum(x * x for x in cvec.values())) or 1
            sim = dot / (nq * nc)
            if sim > 0:
                scored.append((sim, i))
        scored.sort(reverse=True)
        out = []
        for sim, i in scored[:top_k]:
            c = self.chunks[i]
            out.append({
                "text": c["text"], "source": c["source"],
                "section": c["section"], "score": round(sim, 4),
            })
        return out


# 全局单例(启动时 build 一次)
retriever = LocalRetriever()


if __name__ == "__main__":
    # 自检
    for q in ["5000 元入门剪辑配什么显卡", "4K 剪辑内存多少", "电源 4090 要多少瓦"]:
        print("Q:", q)
        for hit in retriever.search(q, top_k=3):
            print(f"   [{hit['score']}] {hit['source']}/{hit['section']}: {hit['text'][:30]}...")
        print()
