# パーキンソン病 FAQボット セットアップ手順

## ファイル構成

```
.
├── faq.csv                  ← FAQデータ（270件）
├── requirements.txt
├── step1_build_index.py     ← 最初に1回だけ実行
├── step2_search.py          ← ローカルでテスト用
├── step3_line_server.py     ← 本番LINE Webhookサーバー
├── setup_rich_menu.py       ← リッチメニュー作成スクリプト（1回実行）
├── rich_menu_bg.png         ← リッチメニュー用画像
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

### GitHub連携（推奨）

1. GitHubにリポジトリをpush
2. Railwayダッシュボード → サービス → Settings → Source でリポジトリを接続
3. ブランチ `main` を選択
4. 以降は `git push origin main` で自動デプロイ

### 環境変数の設定

Railwayダッシュボードの Variables タブで以下を設定：

| 環境変数 | 必須 | 説明 |
|----------|------|------|
| `LINE_CHANNEL_SECRET` | 必須 | LINE Webhook署名検証用 |
| `LINE_CHANNEL_ACCESS_TOKEN` | 必須 | LINE Messaging API認証用 |
| `ANTHROPIC_API_KEY` | 必須 | Claude API認証用 |
| `HEALTHCHECKS_PING_URL` | 任意 | Healthchecks.ioのping URL（15分間隔で送信） |
| `LOG_ACCESS_KEY` | 任意 | ログ閲覧API用のパスワード |

---

## Step 6: Webhook URL設定

Railway のデプロイ後に表示されるURLを LINE Developers の Webhook URL に設定：

```
https://your-app.railway.app/webhook
```

「Webhookの利用」をONにして「検証」ボタンで確認。

---

## Step 7: リッチメニュー設定（1回だけ）

チャット画面下部に「使い方ガイド」「お問い合わせ」ボタンを表示する。

```bash
# リッチメニュー作成
python setup_rich_menu.py

# 削除したい場合
python setup_rich_menu.py --delete
```

リンク先URLは `setup_rich_menu.py` 内の `NOTION_URL` と `FORM_URL` で変更可能。

---

## ログ閲覧

### ログの種類

| ログファイル | 内容 | 記録タイミング |
|-------------|------|---------------|
| `query_log.csv` | 全質問の日時 | 質問があるたび |
| `nofaq_log.csv` | FAQ該当なしの質問・回答 | FAQ未ヒット時のみ |

### ブラウザから確認

環境変数 `LOG_ACCESS_KEY` を設定済みの場合、以下のURLで閲覧可能：

```
https://your-app.railway.app/logs/query?key=あなたのパスワード
https://your-app.railway.app/logs/nofaq?key=あなたのパスワード
```

レスポンス例：

```json
{
  "total": 42,
  "logs": [
    {"日時": "2026-03-20 18:30:00"},
    ...
  ]
}
```

---

## APIエンドポイント一覧

| パス | メソッド | 説明 |
|------|---------|------|
| `/webhook` | POST | LINE Webhook受信 |
| `/health` | GET | ヘルスチェック（Railway用） |
| `/logs/query?key=xxx` | GET | 質問回数ログ |
| `/logs/nofaq?key=xxx` | GET | FAQ該当なしログ |

---

## コスト目安（月100人・1日5問）

| 項目 | 月額 |
|------|------|
| LINE Messaging API | 無料（月1000通まで） |
| Railway | 約750円 |
| Claude Haiku API | 約200〜500円 |
| **合計** | **約1,000〜1,500円** |
