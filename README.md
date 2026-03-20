# パーキンソン病 FAQボット セットアップ手順

## ファイル構成

```
.
├── faq.csv                  ← あなたのFAQデータ（270件）
├── requirements.txt
├── step1_build_index.py     ← 最初に1回だけ実行
├── step2_search.py          ← ローカルでテスト用
├── step3_line_server.py     ← 本番LINE Webhookサーバー
├── faq.index                ← step1実行後に生成される
└── faq_meta.pkl             ← step1実行後に生成される
```

---

## Step 1: 環境構築

```bash
pip install -r requirements.txt
```

---

## Step 2: FAISSインデックス作成（1回だけ）

```bash
# faq.csv をこのフォルダに置いてから実行
python step1_build_index.py
```

完了すると `faq.index` と `faq_meta.pkl` が生成される。

---

## Step 3: 動作確認（ローカル対話テスト）

```bash
export ANTHROPIC_API_KEY=your_key_here
python step2_search.py
```

---

## Step 4: LINE Developers 設定

1. https://developers.line.biz にアクセス
2. 「新規プロバイダー作成」→「Messaging API チャンネル作成」
3. 以下を取得・メモ：
   - `Channel Secret`
   - `Channel Access Token`（長期）

---

## Step 5: Railway にデプロイ

```bash
# Railway CLIインストール
npm install -g @railway/cli

# ログイン
railway login

# プロジェクト作成
railway init

# 環境変数設定
railway variables set LINE_CHANNEL_SECRET=xxxx
railway variables set LINE_CHANNEL_ACCESS_TOKEN=xxxx
railway variables set ANTHROPIC_API_KEY=xxxx

# デプロイ
railway up
```

---

## Step 6: Webhook URL設定

Railway のデプロイ後に表示されるURLを LINE Developers の Webhook URL に設定：

```
https://your-app.railway.app/webhook
```

「Webhookの利用」をONにして「検証」ボタンで確認。

---

## コスト目安（月100人・1日5問）

| 項目 | 月額 |
|------|------|
| LINE Messaging API | 無料（月1000通まで） |
| Railway | 約750円 |
| Claude Haiku API | 約200〜500円 |
| **合計** | **約1,000〜1,500円** |
