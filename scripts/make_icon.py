"""assets/ellview.ico, assets/ellview.png 생성 (한 번만 실행하면 됨)."""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def draw(size: int) -> Image.Image:
    s = size * 4  # 크게 그려서 축소 → 부드러운 가장자리
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = int(s * 0.22)
    # 배경: 남색→보라 세로 그라데이션 둥근 사각형
    grad = Image.new("RGBA", (s, s))
    gd = ImageDraw.Draw(grad)
    top, bot = (58, 78, 196), (126, 74, 214)
    for y in range(s):
        t = y / (s - 1)
        gd.line([(0, y), (s, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], r, fill=255)
    im.paste(grad, (0, 0), mask)
    # 펼친 책 두 장
    m = s * 0.18
    cx = s / 2
    top_y, bot_y = s * 0.26, s * 0.76
    d.polygon([(m, top_y + s * 0.04), (cx - s * 0.02, top_y), (cx - s * 0.02, bot_y), (m, bot_y + s * 0.04)],
              fill=(255, 255, 255, 240))
    d.polygon([(cx + s * 0.02, top_y), (s - m, top_y + s * 0.04), (s - m, bot_y + s * 0.04), (cx + s * 0.02, bot_y)],
              fill=(232, 236, 255, 240))
    # 오른쪽 페이지의 'E' 느낌 줄 3개 + 왼쪽 산 그림(이미지)
    lw = s * 0.045
    for k, y in enumerate((0.38, 0.50, 0.62)):
        x2 = s - m - s * (0.06 if k != 1 else 0.10)
        d.rounded_rectangle([cx + s * 0.08, s * y, x2, s * y + lw], lw / 2, fill=(98, 82, 210, 255))
    d.polygon([(m + s * 0.04, s * 0.66), (m + s * 0.13, s * 0.48), (m + s * 0.20, s * 0.60),
               (m + s * 0.24, s * 0.54), (cx - s * 0.06, s * 0.66)], fill=(98, 82, 210, 255))
    d.ellipse([m + s * 0.15, s * 0.36, m + s * 0.21, s * 0.42], fill=(255, 196, 60, 255))
    return im.resize((size, size), Image.LANCZOS)


def main():
    out = os.path.join(ROOT, "assets")
    os.makedirs(out, exist_ok=True)
    big = draw(256)
    big.save(os.path.join(out, "ellview.png"))
    big.save(os.path.join(out, "ellview.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("saved", out)


if __name__ == "__main__":
    main()
