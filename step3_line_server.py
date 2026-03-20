"""
step3_line_server.py
====================
LINE Messaging API + FAISS検索 + Claude APIを繋いだWebhookサーバー。
step1_build_index.py を先に実行してインデックスを作成してください。

【インストール】
pip install fastapi uvicorn line-bot-sdk sentence-transformers faiss-cpu anthropic

【環境変数（.envファイルまたはRailwayの環境変数に設定）】
LINE_CHANNEL_SECRET=xxxx
LINE_CHANNEL_ACCESS_TOKEN=xxxx
ANTHROPIC_API_KEY=xxxx

【ローカル起動】
uvicorn step3_line_server:app --host 0.0.0.0 --port 8000

【Webhook URL】
https://あなたのドメイン/webhook
"""

import asyncio
import csv
import hashlib
import hmac
import os
import pickle
from base64 import b64decode
from contextlib import asynccontextmanager
from datetime import datetime

import anthropic
import httpx
import faiss
import numpy as np
from fastapi import FastAPI, Header, HTTPException, Request
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import FollowEvent, MessageEvent, TextMessageContent
from sentence_transformers import SentenceTransformer

# ── 設定 ────────────────────────────────────────────────
LINE_CHANNEL_SECRET       = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
HEALTHCHECKS_PING_URL     = os.environ.get("HEALTHCHECKS_PING_URL", "")
LOG_ACCESS_KEY            = os.environ.get("LOG_ACCESS_KEY", "")

INDEX_FILE      = "faq.index"
META_FILE       = "faq_meta.pkl"
MODEL_NAME      = "intfloat/multilingual-e5-small"
TOP_K           = 5
SCORE_THRESHOLD = 0.50
NOFAQ_LOG_FILE  = "nofaq_log.csv"
QUERY_LOG_FILE  = "query_log.csv"
# ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """あなたはパーキンソン病専門の医療従事者向けFAQボットです。

【役割】
医療従事者（医師・看護師・薬剤師・リハビリ職など）からの質問に、提供された参考FAQを最大限活用して回答する。

【回答スタイル】
専門用語を適切に使い、医療従事者向けの表現にする。簡潔・具体的に回答する。

【書式ルール（最重要・必ず守ること）】
回答はLINEチャットに表示される。Markdownは一切使用禁止。以下のルールに厳密に従うこと：

＜絶対に使ってはいけないもの＞
**太字**, # 見出し, ```コードブロック```, - リスト, > 引用, [リンク](url), _イタリック_

＜代わりに使う書式＞
見出し → 「◆」「■」で始める（例：◆ウェアリングオフについて）
箇条書き → 「▸」で始める（例：▸レボドパとの併用が一般的）
強調語句 → 「」で囲む（例：「ドパミン」）
区切り線 → ┈┈┈┈┈┈┈┈┈┈┈┈
注意・警告 → ⚠ で始める

＜回答の構成テンプレート＞
◆ [トピック名]

[本文を2〜4文で簡潔に説明]

▸ ポイント1
▸ ポイント2
▸ ポイント3

┈┈┈┈┈┈┈┈┈┈┈┈
※本回答は参考情報です。

【制約】
診断・処方・投与量の確定的な指示は避ける。FAQに全く関係のない質問には「このFAQの範囲外です」と答える。
"""

WELCOME_MESSAGE = (
    "┏━━━━━━━━━━━━━━┓\n"
    "　🏥 パーキンソン病 FAQボット\n"
    "┗━━━━━━━━━━━━━━┛\n\n"
    "ご登録ありがとうございます。\n"
    "医療従事者の皆さまの日々の\n"
    "疑問にお答えします。\n\n"
    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    "📋 ご質問例\n"
    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    "▸ ウェアリングオフとは？\n"
    "▸ レボドパの服薬タイミングは？\n"
    "▸ DBSの適応基準を教えて\n\n"
    "💡「ヘルプ」と入力すると\n"
    "　使い方を表示します。\n\n"
    "⚠ 本ボットは参考情報の提供のみを\n"
    "　目的としています。"
)

THINKING_MESSAGE = "🔍 回答を準備しております..."

# グローバルリソース（起動時にロード）
resources: dict = {}


async def healthchecks_ping_loop():
    """Healthchecks.ioに5分ごとにpingを送信"""
    url = os.environ.get("HEALTHCHECKS_PING_URL", "")
    print(f"🔍 HEALTHCHECKS_PING_URL 確認: '{url[:20]}...' (len={len(url)})")
    if not url:
        print("⚠ HEALTHCHECKS_PING_URL 未設定 — ping無効")
        return
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await client.get(url, timeout=10)
                print("💓 Healthchecks ping 送信完了")
            except Exception as e:
                print(f"⚠ Healthchecks ping 失敗: {e}")
            await asyncio.sleep(900)  # 15分間隔


@asynccontextmanager
async def lifespan(app: FastAPI):
    """サーバー起動時にモデル・インデックスをロード"""
    print("📦 リソース読み込み中...")
    resources["index"] = faiss.read_index(INDEX_FILE)
    with open(META_FILE, "rb") as f:
        resources["meta"] = pickle.load(f)
    resources["model"] = SentenceTransformer(MODEL_NAME)
    resources["line_config"] = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    resources["parser"] = WebhookParser(LINE_CHANNEL_SECRET)
    resources["claude"] = anthropic.Anthropic()
    print(f"✅ 起動完了: FAQ {resources['index'].ntotal} 件")
    # デバッグ: 環境変数名の一覧を出力
    env_keys = sorted(k for k in os.environ if not k.startswith(("_", "PATH")))
    print(f"🔍 環境変数一覧: {env_keys}")
    # Healthchecks.io pingをバックグラウンドで開始
    ping_task = asyncio.create_task(healthchecks_ping_loop())
    yield
    ping_task.cancel()
    resources.clear()


app = FastAPI(lifespan=lifespan)


# ── FAQ検索 ──────────────────────────────────────────────

def search_faq(query: str) -> list:
    model = resources["model"]
    index = resources["index"]
    meta  = resources["meta"]

    vec = model.encode(
        ["query: " + query],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype("float32")

    scores, indices = index.search(vec, TOP_K)
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if score >= SCORE_THRESHOLD:
            results.append({"score": float(score), "item": meta[idx]})
    return results


def format_context(results: list) -> str:
    if not results:
        return "（関連するFAQが見つかりませんでした）"
    lines = ["【参考FAQ】"]
    for i, r in enumerate(results, 1):
        item = r["item"]
        lines.append(f"\nFAQ{i}（類似度:{r['score']:.2f}）")
        lines.append(f"Q: {item['question']}")
        lines.append(f"A: {item['answer']}")
    return "\n".join(lines)


def log_query():
    """質問回数をCSVに記録"""
    file_exists = os.path.exists(QUERY_LOG_FILE)
    with open(QUERY_LOG_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["日時"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S")])


def log_nofaq(query: str, reply: str):
    """FAQ該当なしの質問と回答をCSVに記録"""
    file_exists = os.path.exists(NOFAQ_LOG_FILE)
    with open(NOFAQ_LOG_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["日時", "質問", "回答"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), query, reply])
    print(f"📝 FAQ該当なしログ記録: {query[:30]}...")


def generate_reply(user_query: str) -> str:
    log_query()
    results = search_faq(user_query)
    context = format_context(results)

    response = resources["claude"].messages.create(
        model="claude-haiku-4-5",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"{context}\n\n【質問】\n{user_query}\n\n医療従事者向けに簡潔に回答してください。",
        }],
    )
    reply = response.content[0].text

    if not results:
        log_nofaq(user_query, reply)

    return reply


# ── LINEルーティング ─────────────────────────────────────

@app.post("/webhook")
async def webhook(
    request: Request,
    x_line_signature: str = Header(alias="X-Line-Signature"),
):
    body = await request.body()

    # 署名検証
    try:
        events = resources["parser"].parse(body.decode(), x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        # ── 友だち追加時のウェルカムメッセージ ──
        if isinstance(event, FollowEvent):
            print("👋 新規フォロー")
            with ApiClient(resources["line_config"]) as api_client:
                line_api = MessagingApi(api_client)
                line_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=WELCOME_MESSAGE)],
                    )
                )
            print("✅ ウェルカムメッセージ送信完了")
            continue

        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessageContent):
            continue

        user_text = event.message.text.strip()
        user_id = event.source.user_id
        print(f"📨 受信: {user_text}")

        # ヘルプコマンド
        if user_text in ("ヘルプ", "help", "使い方"):
            reply_text = (
                "┏━━━━━━━━━━━━━━┓\n"
                "　📖 使い方ガイド\n"
                "┗━━━━━━━━━━━━━━┛\n\n"
                "パーキンソン病に関する質問を\n"
                "自由に入力してください。\n"
                "FAQデータベースから関連情報を\n"
                "検索してお答えします。\n\n"
                "┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                "📋 質問の例\n"
                "┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                "▸ ウェアリングオフとは？\n"
                "▸ レボドパの服薬タイミングは？\n"
                "▸ DBSの適応基準を教えて\n"
                "▸ 嚥下障害への対応は？\n\n"
                "⚠ 本ボットは参考情報の提供のみを\n"
                "　目的としています。"
            )
        else:
            # 「考え中」メッセージを先に送信
            with ApiClient(resources["line_config"]) as api_client:
                line_api = MessagingApi(api_client)
                line_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=THINKING_MESSAGE)],
                    )
                )

            try:
                reply_text = generate_reply(user_text)
            except Exception as e:
                print(f"❌ エラー: {e}")
                reply_text = "申し訳ありません、エラーが発生しました。しばらくしてから再度お試しください。"

        # LINE返信
        with ApiClient(resources["line_config"]) as api_client:
            line_api = MessagingApi(api_client)
            line_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)],
                )
            )
        print(f"✅ 返信完了")

    return {"status": "ok"}


@app.get("/health")
def health():
    """Railway/Renderのヘルスチェック用"""
    return {
        "status": "ok",
        "faq_count": resources.get("index", {}).ntotal if resources.get("index") else 0,
    }


# ── ログ閲覧エンドポイント ────────────────────────────────

def _verify_key(key: str):
    """アクセスキーを検証"""
    if not LOG_ACCESS_KEY:
        raise HTTPException(status_code=403, detail="LOG_ACCESS_KEY not configured")
    if key != LOG_ACCESS_KEY:
        raise HTTPException(status_code=403, detail="Invalid access key")


def _read_csv(filepath: str) -> list[dict]:
    """CSVファイルを読み込んでリスト化"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@app.get("/logs/query")
def get_query_log(key: str = ""):
    """質問回数ログを表示"""
    _verify_key(key)
    rows = _read_csv(QUERY_LOG_FILE)
    return {"total": len(rows), "logs": rows}


@app.get("/logs/nofaq")
def get_nofaq_log(key: str = ""):
    """FAQ該当なしログを表示"""
    _verify_key(key)
    rows = _read_csv(NOFAQ_LOG_FILE)
    return {"total": len(rows), "logs": rows}
