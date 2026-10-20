from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sentinel.datagen.corpus import corpus, docs_before
from sentinel.redact import contains_pii

RUNBOOKS = Path(__file__).resolve().parents[2] / "data" / "runbooks"


def _inc(docs):
    return [d for d in docs if d.doc_id.startswith("INC-")]


def _fa(docs):
    return [d for d in docs if d.doc_id.startswith("FA-")]


def test_corpus_has_28_incidents_22_false_alarms():
    docs = corpus("all", include_test=True)
    assert len(_inc(docs)) == 28
    assert len(_fa(docs)) == 22
    assert {d.source for d in docs} == {"ps02"}


def test_eval_corpus_excludes_test_split():
    docs = corpus()
    assert all(d.split == "train" for d in docs)
    assert len(_inc(docs)) == 16
    assert len(_fa(docs)) == 13
    assert len(_inc(corpus("test", include_test=True))) == 12
    assert len(_fa(corpus("test", include_test=True))) == 9
    assert len(corpus("all", include_test=True)) == 50
    assert corpus("test") == []
    assert len(corpus("train")) == 29


def test_docs_before_excludes_future_and_self():
    ts = datetime(2026, 8, 5, 8, 12)
    docs = docs_before(ts, exclude_id="INC-0007")
    assert docs and all(d.ts < ts for d in docs)
    assert "INC-0007" not in {d.doc_id for d in docs}
    assert "INC-0007" in {d.doc_id for d in docs_before(datetime(2026, 8, 6))}
    assert all(d.split == "train" for d in docs_before(datetime(2026, 9, 1)))
    assert any(d.split == "test" for d in docs_before(datetime(2026, 9, 1), include_test=True))


def test_docs_deterministic():
    assert corpus("all", include_test=True) == corpus("all", include_test=True)


def test_docs_no_pii():
    for d in corpus("all", include_test=True):
        assert not contains_pii(d.text) and not contains_pii(d.fix)
        assert len(d.text.split()) <= 120


def test_every_incident_doc_has_fix_from_runbook():
    for d in _inc(corpus("all", include_test=True)):
        body = (RUNBOOKS / f"{d.code}.md").read_text()
        preventive = body.split("## Preventive action")[1].strip()
        assert d.fix == preventive
        assert d.service in d.text


def test_false_alarm_docs_explain_benign_mechanism():
    docs = {d.doc_id: d for d in corpus("all", include_test=True)}
    t = docs["FA-0010"].text
    assert "false alarm" in t.lower() and "azadi_sale_0814" in t
    assert "unexplained" in docs["FA-0009"].text
    assert "deploy_FA-0003" in docs["FA-0003"].text
    assert "transient" in docs["FA-0001"].text


def test_cascade_doc_mentions_upstream():
    docs = {d.doc_id: d for d in corpus("all", include_test=True)}
    t = docs["INC-0002"].text
    assert docs["INC-0002"].service == "PaymentGateway"
    assert "AuthService" in t and "pool" in t
