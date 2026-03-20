"""
step2_search.py
===============
FAISSインデックスを使ってFAQ類似検索 + Claude APIで回答生成。
step1_build_index.py を先に実行してください。

【実行】
python step2_search.py
"""

import pickle

import anthropic
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# ── 設定 ────────────────────────────────────────────────
INDEX_FILE  = "faq.index"
META_FILE   = "faq_meta.pkl"
MODEL_NAME  = "intfloat/multilingual-e5-small"
TOP_K       = 5      # 類似FAQ上位何件をClaudeに渡すか
SCORE_THRESHOLD = 0.50  # このスコア未満はFAQと無関係とみなす
# ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """あなたはパーキンソン病専門の医療従事者向けFAQボットです。

【役割】
- 医療従事者（医師・看護師・薬剤師・リハビリ職など）からの質問に答える
- 提供された参考FAQを最大限に活用して回答する
- FAQに直接答えがない場合は、関連情報を組み合わせて回答する

【回答スタイル】
- 専門用語を適切に使用し、医療従事者にわかりやすい表現にする
- 簡潔かつ具体的に回答する（箇条書きを適宜使用）
- 必要に応じて「担当医・専門医に相談」を促す

【制約】
- 診断・処方・投与量の確定的な指示は避ける
- FAQに全く関係のない質問には「このFAQの範囲外です」と伝える
"""


def load_resources():
    """インデックスとメタデータをロード"""
    index = faiss.read_index(INDEX_FILE)
    with open(META_FILE, "rb") as f:
        meta = pickle.load(f)
    model = SentenceTransformer(MODEL_NAME)
    print(f"✅ インデックス: {index.ntotal} 件, モデル: {MODEL_NAME}")
    return index, meta, model


def search_faq(query: str, index, meta: list, model: SentenceTransformer, top_k: int = TOP_K):
    """クエリに類似するFAQを検索して返す"""
    vec = model.encode(
        ["query: " + query],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype("float32")

    scores, indices = index.search(vec, top_k)
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if score >= SCORE_THRESHOLD:
            results.append({
                "score": float(score),
                "item": meta[idx],
            })
    return results


def format_faq_context(results: list) -> str:
    """検索結果をClaudeへ渡すプロンプト用テキストに整形"""
    if not results:
        return "（関連するFAQが見つかりませんでした）"

    lines = ["【参考FAQ】"]
    for i, r in enumerate(results, 1):
        item = r["item"]
        cat = f"{item.get('大カテゴリ', '')} > {item.get('小カテゴリ', '')} > {item.get('詳細カテゴリ', '')}"
        lines.append(f"\n--- FAQ {i} （類似度: {r['score']:.2f} | {cat}）---")
        lines.append(f"Q: {item['question']}")
        lines.append(f"A: {item['answer']}")
    return "\n".join(lines)


def ask_claude(user_query: str, faq_context: str) -> str:
    """Claudeに質問 + FAQ文脈を渡して回答を得る"""
    client = anthropic.Anthropic()  # 環境変数 ANTHROPIC_API_KEY を自動参照

    user_message = f"""{faq_context}

---
【質問】
{user_query}

上記の参考FAQをもとに、医療従事者向けに簡潔・正確に回答してください。"""

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def answer(query: str, index, meta, model) -> str:
    """検索 → 回答生成のメイン処理"""
    results = search_faq(query, index, meta, model)
    faq_context = format_faq_context(results)

    # デバッグ用：どのFAQがヒットしたか表示
    if results:
        print(f"\n🔍 ヒットしたFAQ ({len(results)}件):")
        for r in results:
            print(f"  [{r['score']:.2f}] {r['item']['question']}")
    else:
        print("\n⚠️  類似FAQなし（スコア閾値未満）")

    return ask_claude(query, faq_context)


def main():
    index, meta, model = load_resources()

    print("\n" + "="*50)
    print("パーキンソン病 FAQボット（テストモード）")
    print("終了するには 'quit' と入力")
    print("="*50)

    while True:
        query = input("\n質問: ").strip()
        if query.lower() in ("quit", "exit", "q"):
            break
        if not query:
            continue

        print("\n💬 回答生成中...")
        reply = answer(query, index, meta, model)
        print(f"\n【回答】\n{reply}")


if __name__ == "__main__":
    main()
