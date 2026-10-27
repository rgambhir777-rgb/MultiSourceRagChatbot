"""Measure retrieval quality on the golden set, for each search strategy.

    python -m app.cli ingest data/sample_docs     # the knowledge base must be indexed first
    python -m evals.retrieval_eval                # prints the comparison table
    python -m evals.retrieval_eval --show-misses  # also lists questions that were missed

No OpenAI calls: this measures search only, so it is free and runs offline.
"""

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.logging_setup import configure_logging
from app.retrieval.embeddings import Embedder
from app.retrieval.reranker import Reranker
from app.retrieval.retriever import Retriever
from app.retrieval.vectorstore import SearchMode, VectorStore
from evals.metrics import first_correct_rank, hit_at_k, mean_reciprocal_rank

GOLDEN = Path(__file__).parent / "datasets" / "golden.jsonl"
TOP_K = 5
STRATEGIES: list[tuple[str, SearchMode, bool]] = [
    ("dense only", "dense", False),
    ("sparse (BM25) only", "sparse", False),
    ("hybrid (RRF)", "hybrid", False),
    ("hybrid + rerank", "hybrid", True),
]


@dataclass(frozen=True)
class StrategyResult:
    name: str
    ranks: list[int | None]
    latencies_ms: list[float]


def load_golden(path: Path = GOLDEN) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def run_strategy(
    retriever: Retriever, golden: list[dict[str, str]], name: str, mode: SearchMode, rerank: bool
) -> StrategyResult:
    ranks, latencies = [], []
    for item in golden:
        started = time.perf_counter()
        chunks = retriever.retrieve(item["question"], mode=mode, rerank=rerank, top_k=TOP_K)
        latencies.append((time.perf_counter() - started) * 1000)
        results = [(c.source, c.text) for c in chunks]
        ranks.append(first_correct_rank(results, item["expected_source"], item["expected_phrase"]))
    return StrategyResult(name, ranks, latencies)


def print_table(results: list[StrategyResult], questions: int) -> None:
    print(f"\nRetrieval quality on {questions} golden questions (top {TOP_K} results)\n")
    print(f"{'strategy':<20} {'hit@1':>6} {'hit@3':>6} {'hit@5':>6} {'MRR':>6} {'median ms':>10}")
    for r in results:
        print(
            f"{r.name:<20} {hit_at_k(r.ranks, 1):>6.2f} {hit_at_k(r.ranks, 3):>6.2f} "
            f"{hit_at_k(r.ranks, 5):>6.2f} {mean_reciprocal_rank(r.ranks):>6.2f} "
            f"{statistics.median(r.latencies_ms):>10.0f}"
        )


def print_misses(results: list[StrategyResult], golden: list[dict[str, str]]) -> None:
    for r in results:
        missed = [g for g, rank in zip(golden, r.ranks, strict=True) if rank != 1]
        if missed:
            print(f"\n{r.name}: not ranked first")
            for g, rank in ((g, r.ranks[golden.index(g)]) for g in missed):
                print(f"  [{g['id']}] rank={rank or '-'}  {g['question']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare retrieval strategies on the golden set.")
    parser.add_argument("--show-misses", action="store_true")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    configure_logging("WARNING")

    settings = get_settings()
    embedder = Embedder(settings)
    store = VectorStore.from_settings(settings, embedder.dense_size)
    retriever = Retriever(settings, embedder, store, Reranker(settings))
    golden = load_golden()
    if store.count() == 0:
        print("The knowledge base is empty. Run: python -m app.cli ingest data/sample_docs")
        return 1

    retriever.retrieve("warm-up")  # first call pays one-time model start-up costs
    results = [run_strategy(retriever, golden, *strategy) for strategy in STRATEGIES]
    print_table(results, len(golden))
    if args.show_misses:
        print_misses(results, golden)
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
