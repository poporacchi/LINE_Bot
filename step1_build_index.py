"""
step1_build_index.py
====================
FAQデータ（CSV）をベクトル化してFAISSインデックスを作成する。
※最初に一度だけ実行する。

【インストール】
pip install sentence-transformers faiss-cpu pandas numpy

【実行】
python step1_build_index.py
"""

import pickle
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

# ── 設定 ────────────────────────────────────────────────
FAQ_CSV    = "faq.csv"       # 入力CSV（このスクリプトと同じフォルダに置く）
INDEX_FILE = "faq.index"     # FAISSインデックス保存先
META_FILE  = "faq_meta.pkl"  # QAメタデータ保存先

# 多言語対応・軽量モデル（日本語OK、初回実行時に自動ダウンロード約130MB）
MODEL_NAME = "intfloat/multilingual-e5-small"
# ────────────────────────────────────────────────────────


def load_faq(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    # 列名の確認
    print(f"列名: {df.columns.tolist()}")
    df = df.rename(columns={
        "質問 (Q)": "question",
        "回答 (A)":  "answer",
    })
    df = df.dropna(subset=["question", "answer"]).reset_index(drop=True)
    print(f"✅ FAQ読み込み完了: {len(df)} 件")
    return df


def build_embeddings(questions: list[str], model: SentenceTransformer) -> np.ndarray:
    """質問をベクトル化（E5モデルは 'query: ' プレフィックスを付けると精度UP）"""
    texts = ["query: " + q for q in questions]
    print(f"🔄 ベクトル化中 ({len(texts)} 件)...")
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,  # コサイン類似度に最適化
        convert_to_numpy=True,
    )
    print(f"✅ ベクトル化完了: shape={embeddings.shape}")
    return embeddings.astype("float32")


def main():
    # 1. FAQデータ読み込み
    df = load_faq(FAQ_CSV)

    # 2. モデルロード
    print(f"\n📦 モデルをロード中: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    # 3. ベクトル化
    embeddings = build_embeddings(df["question"].tolist(), model)

    # 4. FAISSインデックス作成（IndexFlatIP = 内積 = 正規化済みならコサイン類似度）
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    print(f"✅ FAISSインデックス作成: {index.ntotal} 件登録")

    # 5. 保存
    faiss.write_index(index, INDEX_FILE)
    print(f"💾 インデックス保存: {INDEX_FILE}")

    # QAテキストと全カラムをpickleで保存
    meta = df.to_dict(orient="records")
    with open(META_FILE, "wb") as f:
        pickle.dump(meta, f)
    print(f"💾 メタデータ保存: {META_FILE}")
    print("\n🎉 完了！次は step2_search.py を実行してください。")


if __name__ == "__main__":
    main()
