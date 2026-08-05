"""Benchmark: MiniLM (sekarang) vs multilingual-e5-small.

Mengukur untuk tiap model:
1. RAM usage (baseline -> setelah load model -> saat encode/query)
2. Distance parafrase "vlan itu apa?" vs "Apa itu VLAN?" (target < 0.3)
3. Cache hit rate pada kumpulan pertanyaan + varian parafrase (threshold 0.25)

Jalankan: python tests/benchmark_embedding.py
"""

from __future__ import annotations

import time

import numpy as np
import psutil
from sentence_transformers import SentenceTransformer

MINILM = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
E5_SMALL = "intfloat/multilingual-e5-small"

THRESHOLD = 0.25  # sama dengan SemanticCache

# Pasangan untuk mengukur distance semantik
PAIRS = [
    ("Apa itu VLAN?", "vlan itu apa?"),              # kasus yang gagal di MiniLM (0.59)
    ("Apa itu VLAN?", "jelaskan apa itu VLAN"),       # parafrase ringan (0.03 di MiniLM)
    ("Apa itu VLAN?", "apa itu vlan"),
    ("Apa itu VLAN?", "bagaimana cara kerja routing?"),  # harus tetap JAUH
]

# Pertanyaan dasar + varian parafrase (untuk hit rate cache)
BASE_QUESTIONS = [
    "Apa itu VLAN?",
    "Bagaimana cara kerja routing?",
    "Apa itu keamanan jaringan?",
]
VARIANTS = {
    "Apa itu VLAN?": [
        "vlan itu apa?", "jelaskan vlan", "apa pengertian vlan",
        "apa itu vlan", "jelaskan apa itu VLAN",
    ],
    "Bagaimana cara kerja routing?": [
        "routing bekerja bagaimana?", "jelaskan routing", "apa itu proses routing",
        "cara kerja routing", "jelaskan cara kerja routing",
    ],
    "Apa itu keamanan jaringan?": [
        "keamanan jaringan itu apa?", "jelaskan keamanan jaringan",
        "apa itu keamanan jaringan", "keamanan jaringan",
        "apa yang dimaksud keamanan jaringan",
    ],
}


def rss_mb() -> float:
    return psutil.Process().memory_info().rss / 1024 / 1024


def evaluate(model_name: str) -> dict:
    base_ram = rss_mb()
    t0 = time.time()
    model = SentenceTransformer(model_name)
    load_time = time.time() - t0
    load_ram = rss_mb()

    pair_dists = []
    for q, v in PAIRS:
        embs = model.encode([q, v], normalize_embeddings=True)
        pair_dists.append(float(1 - np.dot(embs[0], embs[1])))

    # hit rate cache (query vs varian, threshold sama seperti SemanticCache)
    t0 = time.time()
    base_embs = model.encode(BASE_QUESTIONS, normalize_embeddings=True)
    hits = total = 0
    for base_q, variants in VARIANTS.items():
        base_emb = base_embs[BASE_QUESTIONS.index(base_q)]
        for ve in model.encode(variants, normalize_embeddings=True):
            total += 1
            if 1 - float(np.dot(base_emb, ve)) <= THRESHOLD:
                hits += 1
    hit_rate = hits / total
    encode_time = time.time() - t0
    query_ram = rss_mb()

    return {
        "model": model_name,
        "base_ram": base_ram,
        "load_ram": load_ram,
        "query_ram": query_ram,
        "ram_delta_load": load_ram - base_ram,
        "pair_dists": dict(zip([f"{q} | {v}" for q, v in PAIRS], pair_dists, strict=True)),
        "hit_rate": hit_rate,
        "load_time_s": load_time,
        "encode_time_s": encode_time,
    }


def main() -> None:
    results = {}
    for name in (MINILM, E5_SMALL):
        print(f"\n=== Loading {name} ===")
        results[name] = evaluate(name)

    def show(label: str, fmt, key) -> None:
        a = fmt(results[MINILM][key])
        b = fmt(results[E5_SMALL][key])
        print(f"{label:<32} MiniLM={a:<16} e5-small={b}")

    print("\n" + "=" * 72)
    show("RAM baseline (MB)", lambda v: f"{v:.0f}", "base_ram")
    show("RAM setelah load (MB)", lambda v: f"{v:.0f}", "load_ram")
    show("Delta RAM load (MB)", lambda v: f"{v:.0f}", "ram_delta_load")
    show("RAM saat query (MB)", lambda v: f"{v:.0f}", "query_ram")
    show("Load time (s)", lambda v: f"{v:.1f}", "load_time_s")
    show("Encode 15 kalimat (s)", lambda v: f"{v:.2f}", "encode_time_s")
    show("Cache hit rate", lambda v: f"{v*100:.0f}%", "hit_rate")

    print("\nDistance pasangan:")
    keys = list(results[MINILM]["pair_dists"].keys())
    for k in keys:
        a = results[MINILM]["pair_dists"][k]
        b = results[E5_SMALL]["pair_dists"][k]
        print(f"  {k:<62} MiniLM={a:.3f}  e5={b:.3f}")

    # Kriteria
    e5 = results[E5_SMALL]
    mini = results[MINILM]
    crit1 = e5["load_ram"] <= 500
    crit2 = e5["pair_dists"]["Apa itu VLAN? | vlan itu apa?"] < 0.3
    crit3 = (e5["hit_rate"] - mini["hit_rate"]) >= 0.10
    print("\n" + "=" * 72)
    print(f"Kriteria 1  RAM load <= 500MB          : {'PASS' if crit1 else 'FAIL'} ({e5['load_ram']:.0f} MB)")
    print(f"Kriteria 2  dist 'vlan itu apa?' < 0.3 : {'PASS' if crit2 else 'FAIL'} ({e5['pair_dists']['Apa itu VLAN? | vlan itu apa?']:.3f})")
    print(f"Kriteria 3  hit rate naik >= 10%       : {'PASS' if crit3 else 'FAIL'} ({mini['hit_rate']*100:.0f}% -> {e5['hit_rate']*100:.0f}%)")
    verdict = "GANTI ke e5-small" if (crit1 and crit2 and crit3) else "REVERT / tetap MiniLM"
    print(f"\nKeputusan: {verdict}")


if __name__ == "__main__":
    main()
