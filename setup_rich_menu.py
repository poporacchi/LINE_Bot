"""
setup_rich_menu.py
==================
LINE リッチメニューを作成・登録するワンタイムスクリプト。
チャット画面下部に「使い方ガイド」「お問い合わせ」ボタンを表示します。

【使い方】
1. .env に LINE_CHANNEL_ACCESS_TOKEN を設定
2. python setup_rich_menu.py
3. 完了後は再実行不要（LINEサーバーに永続保存されます）

【リッチメニューを削除したい場合】
python setup_rich_menu.py --delete
"""

import io
import os
import sys

# Windows コンソールでUTF-8を使用
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import httpx
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
BASE_URL = "https://api.line.me/v2/bot"
DATA_URL = "https://api-data.line.me/v2/bot"

NOTION_URL = "https://splashy-kryptops-b2f.notion.site/FAQ-LINE-3291d052b0a580c79d40d3ad81c78bad?openExternalBrowser=1"
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdcs9N-n4vtf88899GxOEKVC5Z8D5jiS90DmaZIMAgio3H3FA/viewform?openExternalBrowser=1"

HEADERS = {
    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
}


def create_rich_menu_image() -> bytes:
    """リッチメニュー用の画像を生成（2500x843px）
    プロジェクト直下に rich_menu_bg.png があればそれを優先的に読み込みます。
    """
    REQUIRED_W, REQUIRED_H = 2500, 843
    image_path = "rich_menu_bg.png"
    if os.path.exists(image_path):
        print(f"  ローカル画像を使用します: {image_path}")
        img = Image.open(image_path)
        if img.size != (REQUIRED_W, REQUIRED_H):
            print(f"  リサイズ: {img.size} → {REQUIRED_W}x{REQUIRED_H}")
            img = img.resize((REQUIRED_W, REQUIRED_H), Image.LANCZOS)
        if img.mode == "RGBA":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        print(f"  ファイルサイズ: {buf.tell() / 1024:.0f} KB")
        return buf.getvalue()

    print("  ローカル画像が見つからないため、動的に生成します")
    W, H = 2500, 843
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    # 左半分: 青（使い方ガイド）
    draw.rectangle([0, 0, 1249, H], fill=(41, 98, 255))
    # 右半分: 緑（お問い合わせ）
    draw.rectangle([1250, 0, W, H], fill=(0, 168, 107))
    # 区切り線
    draw.line([(1250, 80), (1250, H - 80)], fill="white", width=4)

    # フォント設定
    try:
        # Linux (Railway/Nixpacks)
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 64)
        font_icon = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 80)
    except OSError:
        try:
            # Windows
            font_large = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 64)
            font_icon = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 80)
        except OSError:
            try:
                # macOS
                font_large = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", 64)
                font_icon = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", 80)
            except OSError:
                font_large = ImageFont.load_default()
                font_icon = font_large

    # 左側: 使い方ガイド
    draw.text((625, H // 2 - 70), "📖", fill="white", font=font_icon, anchor="mm")
    draw.text((625, H // 2 + 60), "使い方ガイド", fill="white", font=font_large, anchor="mm")

    # 右側: お問い合わせ
    draw.text((1875, H // 2 - 70), "✉️", fill="white", font=font_icon, anchor="mm")
    draw.text((1875, H // 2 + 60), "お問い合わせ", fill="white", font=font_large, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_default_rich_menu() -> str | None:
    """現在のデフォルトリッチメニューIDを取得"""
    resp = httpx.get(f"{BASE_URL}/user/all/richmenu", headers=HEADERS)
    if resp.status_code == 200:
        return resp.json().get("richMenuId")
    return None


def delete_all_rich_menus():
    """全リッチメニューを削除"""
    # デフォルト解除
    httpx.delete(f"{BASE_URL}/user/all/richmenu", headers=HEADERS)

    # 全メニュー取得・削除
    resp = httpx.get(f"{BASE_URL}/richmenu/list", headers=HEADERS)
    if resp.status_code == 200:
        menus = resp.json().get("richmenus", [])
        for menu in menus:
            rid = menu["richMenuId"]
            httpx.delete(f"{BASE_URL}/richmenu/{rid}", headers=HEADERS)
            print(f"  削除: {rid}")
    print("✅ 全リッチメニューを削除しました")


def create_rich_menu():
    """リッチメニューを作成・画像アップロード・デフォルト設定"""

    # 既存チェック
    existing = get_default_rich_menu()
    if existing:
        print(f"⚠ デフォルトリッチメニューが既に存在します: {existing}")
        ans = input("上書きしますか？ (y/N): ").strip().lower()
        if ans != "y":
            print("中止しました")
            return
        delete_all_rich_menus()

    # 1. リッチメニュー作成
    print("📋 リッチメニューを作成中...")
    rich_menu_data = {
        "size": {"width": 2500, "height": 843},
        "selected": True,
        "name": "パキサポ FAQボット メニュー",
        "chatBarText": "メニューを開く",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": 1250, "height": 843},
                "action": {
                    "type": "uri",
                    "label": "使い方ガイド",
                    "uri": NOTION_URL,
                },
            },
            {
                "bounds": {"x": 1250, "y": 0, "width": 1250, "height": 843},
                "action": {
                    "type": "uri",
                    "label": "お問い合わせ",
                    "uri": FORM_URL,
                },
            },
        ],
    }

    resp = httpx.post(
        f"{BASE_URL}/richmenu",
        headers={**HEADERS, "Content-Type": "application/json"},
        json=rich_menu_data,
    )
    resp.raise_for_status()
    rich_menu_id = resp.json()["richMenuId"]
    print(f"  作成完了: {rich_menu_id}")

    # 2. 画像アップロード
    print("🖼️ 画像をアップロード中...")
    image_data = create_rich_menu_image()
    resp = httpx.post(
        f"{DATA_URL}/richmenu/{rich_menu_id}/content",
        headers={**HEADERS, "Content-Type": "image/jpeg"},
        content=image_data,
    )
    resp.raise_for_status()
    print("  アップロード完了")

    # 3. デフォルトに設定
    print("⚙️ デフォルトメニューに設定中...")
    resp = httpx.post(
        f"{BASE_URL}/user/all/richmenu/{rich_menu_id}",
        headers=HEADERS,
    )
    resp.raise_for_status()
    print(f"✅ リッチメニュー設定完了！")
    print(f"   メニューID: {rich_menu_id}")


if __name__ == "__main__":
    if "--delete" in sys.argv:
        delete_all_rich_menus()
    else:
        create_rich_menu()
