"""RAG memory: past postmortems (train split only) + runbooks, embedded with OPENAI_EMBED_MODEL.

`search` returns the top-k documents; the runtime injects them into the Commander prompt as retrieved context and
cites them by evidence id. Falls back to TF-IDF when embeddings are unavailable (LLM off / outage). Feedback 👍 adds
the confirmed RCA as a new document, so the memory grows from operator feedback.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import yaml

from sentinel.agents.tools import Memory
from sentinel.config import settings
from sentinel.datagen.corpus import corpus


@dataclass
class Doc:
    id: str
    kind: str  # postmortem | runbook | feedback
    code: str
    service: str
    title: str
    text: str
    fix: str = ""
    label: str = "incident"
    vec: list[float] | None = field(default=None, repr=False)

    # Memory (TF-IDF) compatibility
    @property
    def metric(self) -> str:
        return ""


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class RagStore:
    def __init__(self) -> None:
        self.docs: list[Doc] = [
            Doc(d.id, "postmortem", d.code, d.service, f"{d.id} ({d.code})", d.text, d.fix, d.label)
            for d in corpus("train")
        ]
        with (settings.config_dir / "runbooks.yaml").open() as f:
            for rb in yaml.safe_load(f)["runbooks"]:
                self.docs.append(Doc(rb["id"], "runbook", rb["code"], "*", rb["title"], rb["text"]))
        self.tfidf = Memory(self.docs)  # duck-typed: needs .text .code .service .metric
        self.embedded = False

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        from sentinel.agents.llm import client

        r = await client().embeddings.create(model=settings.openai_embed_model, input=texts)
        return [d.embedding for d in r.data]

    async def ensure_embedded(self) -> bool:
        if self.embedded:
            return True
        if not (settings.openai_api_key and settings.openai_embed_model):
            return False
        try:
            vecs = await self._embed([f"{d.title}. {d.text} {d.fix}" for d in self.docs])
        except Exception:  # noqa: BLE001 — fall back to TF-IDF
            return False
        for d, v in zip(self.docs, vecs, strict=True):
            d.vec = v
        self.embedded = True
        return True

    async def search(
        self, query: str, service: str, k: int = 4, use_embeddings: bool = True
    ) -> tuple[list[tuple[Doc, float]], str]:
        if use_embeddings and await self.ensure_embedded():
            try:
                (qv,) = await self._embed([query])
                scored = [(d, _cos(qv, d.vec) + 0.05 * (d.service == service)) for d in self.docs if d.vec]
                return sorted(scored, key=lambda t: -t[1])[:k], "embeddings"
            except Exception as e:  # noqa: BLE001 — fall back to TF-IDF
                print("rag: embedding query failed, using tfidf:", type(e).__name__)
        return [(d, s) for d, s in self.tfidf.search(query, service, k)], "tfidf"

    async def add(self, doc: Doc) -> int:
        if self.embedded:
            try:
                (doc.vec,) = await self._embed([f"{doc.title}. {doc.text} {doc.fix}"])
            except Exception:  # noqa: BLE001
                doc.vec = None
        self.docs.append(doc)
        self.tfidf = Memory(self.docs)
        return len(self.docs)
