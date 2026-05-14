"""
thumbnail_generator.py — DALL-E 3 で背景画像を生成し、Pillow で日本語タイトルを合成する。

note のサムネ推奨比率は 1280×670(約 1.91:1) なので
DALL-E 3 の 1792×1024 (16:9) を生成→クロップで対応する。
"""

from __future__ import annotations

import io
import logging
import os
import textwrap
from pathlib import Path
from typing import Literal

import requests
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import cost_guard

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
NOTE_THUMB_W, NOTE_THUMB_H = 1280, 670

# ============================================================
# ブランド統一テンプレ — 一覧画面で「あの人の記事だ」と認識される共通要素
# ============================================================
BRAND_NAME = os.environ.get("BRAND_NAME", "金融トレンド徹底解剖")
# 共通ブランドカラー(左ストライプ・カテゴリバッジ枠の色味)
BRAND_PRIMARY = (15, 30, 60)          # 濃紺
BRAND_ACCENT  = (255, 195, 0)         # ゴールド
BRAND_FRAME_PX = 8                    # 外枠の幅

CATEGORY_EN = {
    "stock":  "stock market",
    "fx":     "forex",
    "crypto": "cryptocurrency",
}

# 日本語フォントの候補(GitHub Actions の Ubuntu に存在するもの優先)
JP_FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    # WSL / macOS / Windows のフォールバック
    "/mnt/c/Windows/Fonts/YuGothB.ttc",
    "/mnt/c/Windows/Fonts/meiryob.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W7.ttc",
)


def _find_jp_font(size: int) -> ImageFont.FreeTypeFont:
    for path in JP_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    log.warning("No Japanese font found; falling back to default")
    return ImageFont.load_default()


# ----------------------------------------------------------------------
# DALL-E 呼び出し
# ----------------------------------------------------------------------

def _load_prompt(topic: str, category: str) -> str:
    template = (PROMPTS_DIR / "thumbnail_prompt.md").read_text(encoding="utf-8")
    return template.replace(
        "{{TOPIC}}", topic
    ).replace(
        "{{CATEGORY_EN}}", CATEGORY_EN.get(category, "finance")
    )


def _gradient_background(category: str) -> Image.Image:
    """Pillow-only fallback when DALL-E is not configured.
    Produces a clean two-tone gradient with a faint category tag.
    """
    # 1792x1024 to match the DALL-E output dimensions so the rest of the
    # pipeline (crop, title composition) keeps working unchanged.
    w, h = 1792, 1024
    # Category-tinted accent layered on top of the brand navy.
    accent = {
        "stock":  (0, 120, 180),
        "fx":     (0, 150, 110),
        "crypto": (180, 120, 0),
    }.get(category, (60, 90, 160))
    base = Image.new("RGB", (w, h), BRAND_PRIMARY)
    overlay = Image.new("RGB", (w, h), accent)
    # Vertical alpha mask: top accent → bottom brand color.
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    for y in range(h):
        md.line([(0, y), (w, y)], fill=int(255 * (1 - y / h)))
    base.paste(overlay, (0, 0), mask)
    return base.filter(ImageFilter.GaussianBlur(radius=2))


def _generate_background(topic: str, category: str) -> Image.Image:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.warning("OPENAI_API_KEY not set — using Pillow-only gradient background.")
        return _gradient_background(category)

    client = OpenAI(api_key=api_key)
    prompt = _load_prompt(topic, category)

    log.info("Calling DALL-E 3 ...")
    resp = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024",  # 16:9
        quality="standard",
        n=1,
    )
    # コスト記録
    try:
        cost_guard.record(cost_guard.dalle_cost(images=1))
    except Exception as e:
        log.warning("cost recording failed: %s", e)

    url = resp.data[0].url
    img_bytes = requests.get(url, timeout=60).content
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


# ----------------------------------------------------------------------
# タイトル合成
# ----------------------------------------------------------------------

def _crop_to_note_ratio(img: Image.Image) -> Image.Image:
    """1792×1024 → 1280×670 にリサイズ&中央クロップ。"""
    src_w, src_h = img.size
    target_ratio = NOTE_THUMB_W / NOTE_THUMB_H
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        # 横が長すぎ → 左右を削る
        new_w = int(src_h * target_ratio)
        offset = (src_w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        offset = (src_h - new_h) // 2
        img = img.crop((0, offset, src_w, offset + new_h))
    return img.resize((NOTE_THUMB_W, NOTE_THUMB_H), Image.LANCZOS)


def _add_overlay(img: Image.Image, title: str, category: str) -> Image.Image:
    """ブランド統一テンプレ: 外枠+左サイドバー+巨大数字+タイトル+ブランド名。"""
    img = img.copy().convert("RGBA")

    # 1) 左半分に強い暗転オーバーレイ(白タイトルの可読性確保)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    band_w = int(NOTE_THUMB_W * 0.62)
    for x in range(band_w):
        alpha = int(220 * (1 - x / band_w * 0.5))
        draw.line([(x, 0), (x, NOTE_THUMB_H)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)

    # ★ ブランド共通要素 ① 外枠フレーム(全画像で必ず付く)
    for i in range(BRAND_FRAME_PX):
        draw.rectangle(
            [(i, i), (NOTE_THUMB_W - 1 - i, NOTE_THUMB_H - 1 - i)],
            outline=BRAND_ACCENT + (255,),
        )

    # ★ ブランド共通要素 ② 左サイドバー(ブランドカラーのストライプ)
    bar_w = 14
    draw.rectangle(
        [(BRAND_FRAME_PX, BRAND_FRAME_PX),
         (BRAND_FRAME_PX + bar_w, NOTE_THUMB_H - BRAND_FRAME_PX)],
        fill=BRAND_ACCENT + (255,),
    )

    # 2) カテゴリバッジ(左上、強配色)
    # Linuxの IPAGothic/NotoSansCJK は絵文字グリフを持たないので
    # シンボル文字(常に表示可)に置換。
    cat_label = {"stock": "▲ 株式トレンド", "fx": "¥ FX市況",
                 "crypto": "₿ 暗号資産"}.get(category, "■ 金融")
    cat_color = {"stock": (0, 200, 90), "fx": (255, 195, 0),
                 "crypto": (0, 240, 255)}.get(category, (180, 180, 180))
    tag_font = _find_jp_font(34)
    bbox = draw.textbbox((0, 0), cat_label, font=tag_font)
    pad_x, pad_y = 22, 10
    tag_w = bbox[2] - bbox[0] + pad_x * 2
    tag_h = bbox[3] - bbox[1] + pad_y * 2
    draw.rounded_rectangle(
        [(40, 40), (40 + tag_w, 40 + tag_h)],
        radius=8, fill=cat_color + (255,),
    )
    draw.text((40 + pad_x, 40 + pad_y - bbox[1]),
              cat_label, font=tag_font, fill=(0, 0, 0))

    # 3) 数字検出 → 巨大表示(YouTubeサムネ風)
    big_number = _extract_big_number(title)
    if big_number:
        big_font = _find_jp_font(180)
        bbox = draw.textbbox((0, 0), big_number, font=big_font)
        nw, nh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        nx = 50
        ny = 110
        # 縁取り(黒3px)+ アクセント色
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                if dx*dx + dy*dy <= 16:
                    draw.text((nx + dx, ny + dy), big_number,
                              font=big_font, fill=(0, 0, 0))
        draw.text((nx, ny), big_number, font=big_font, fill=cat_color)
        title_start_y = ny + nh + 20
    else:
        title_start_y = 130

    # 4) タイトル本体(左寄せ・最大 4 行に拡張、フォントも縮めて切れにくくする)
    title_clean = _strip_brackets(title).replace(big_number or "", "", 1).strip()
    title_font = _find_jp_font(48)
    wrapped = _wrap_title(title_clean, max_per_line=17, max_lines=4)
    line_h = 60

    for i, line in enumerate(wrapped):
        y = title_start_y + i * line_h
        # 強い黒縁取り
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx*dx + dy*dy <= 9:
                    draw.text((50 + dx, y + dy), line,
                              font=title_font, fill=(0, 0, 0))
        draw.text((50, y), line, font=title_font, fill=(255, 255, 255))

    # ★ ブランド共通要素 ③ 右下のブランド名(固定位置・固定フォント)
    brand = f"@{BRAND_NAME}"
    brand_font = _find_jp_font(26)
    bbox = draw.textbbox((0, 0), brand, font=brand_font)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # 半透明黒の角丸背景 → ブランド名は白
    bx = NOTE_THUMB_W - bw - 50
    by = NOTE_THUMB_H - bh - 40
    draw.rounded_rectangle(
        [(bx - 14, by - 8), (bx + bw + 14, by + bh + 12)],
        radius=6, fill=(0, 0, 0, 180),
    )
    draw.text((bx, by), brand, font=brand_font, fill=BRAND_ACCENT)

    return img.convert("RGB")


def _extract_big_number(title: str) -> str | None:
    """タイトルから巨大表示する数字を抽出(例: 「7つの」→「7」, 「年50万円」→「50万」)."""
    import re
    # パターン優先: N 万円 / N つの / 数字+単位
    patterns = [
        r"(\d{1,3})\s*万円",
        r"(\d{1,3})\s*兆",
        r"(\d{1,3})\s*億",
        r"(\d{1,3})\s*%",
        r"(\d{1,2})\s*つの",
        r"(\d{4})\s*年",
    ]
    suffix_map = {
        "万円": "万", "兆": "兆", "億": "億", "%": "%",
        "つの": "", "年": "年",
    }
    for pat in patterns:
        m = re.search(pat, title)
        if m:
            num = m.group(1)
            for suf, label in suffix_map.items():
                if suf in pat:
                    return f"{num}{label}"
            return num
    # 単独の数字
    m = re.search(r"(\d{1,3})", title)
    return m.group(1) if m else None


def _strip_brackets(title: str) -> str:
    """先頭の【...】を取り除く(バッジ的役割は別 UI が担うため)."""
    import re
    return re.sub(r"^[【\[][^】\]]+[】\]]\s*", "", title).strip()


def _wrap_title(title: str, max_per_line: int, max_lines: int) -> list[str]:
    """日本語タイトルを N 文字ごとに改行(単語分断OKだが句読点優先)."""
    if len(title) <= max_per_line:
        return [title]

    lines = []
    remaining = title
    while remaining and len(lines) < max_lines:
        if len(remaining) <= max_per_line:
            lines.append(remaining)
            break
        # 句読点で切れる位置を優先
        cut = max_per_line
        for i in range(max_per_line, max_per_line - 5, -1):
            if i < len(remaining) and remaining[i] in "、。!?・ 　":
                cut = i + 1
                break
        lines.append(remaining[:cut])
        remaining = remaining[cut:]

    if remaining and len(lines) == max_lines:
        # 末尾を ... で省略
        last = lines[-1]
        if len(last) > max_per_line - 1:
            last = last[: max_per_line - 1]
        lines[-1] = last + "…"

    return lines


# ----------------------------------------------------------------------
# 公開関数
# ----------------------------------------------------------------------

def generate(topic: str, category: Literal["stock", "fx", "crypto"],
             title: str, out_path: str | Path) -> Path:
    """サムネを生成して out_path に保存し、Path を返す。"""
    bg = _generate_background(topic, category)
    bg = _crop_to_note_ratio(bg)
    final = _add_overlay(bg, title, category)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(out_path, "PNG", quality=92)
    log.info("thumbnail saved: %s", out_path)
    return out_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    p = generate(
        topic="Bitcoin halving rally",
        category="crypto",
        title="ビットコイン半減期後の上昇トレンドはいつまで続くのか",
        out_path="output/sample_thumbnail.png",
    )
    print("saved:", p)
