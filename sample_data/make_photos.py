# 테스트용 합성 설치 사진 4장 생성 (실제 현장 사진 아님). 글자·번호·IP는 넣지 않는다.
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1080, 1350
random.seed(7)


def grain(img, amt=10):
    px = img.load()
    for _ in range(W * H // 6):
        x, y = random.randrange(W), random.randrange(H)
        r, g, b = px[x, y]
        d = random.randint(-amt, amt)
        px[x, y] = (max(0, min(255, r + d)), max(0, min(255, g + d)), max(0, min(255, b + d)))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def vgrad(d, box, top, bot):
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0)
        d.line((x0, y, x1, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bot)))


def cable(d, p0, p1, color, w=9, sag=80):
    pts = []
    for i in range(31):
        t = i / 30
        x = p0[0] + (p1[0] - p0[0]) * t
        y = p0[1] + (p1[1] - p0[1]) * t + sag * 4 * t * (1 - t)
        pts.append((x, y))
    d.line(pts, fill=color, width=w, joint="curve")


def ports(d, x, y, n, size=34, gap=10):
    for i in range(n):
        px = x + i * (size + gap)
        d.rectangle((px, y, px + size, y + size * 0.8), fill="#1d1f24", outline="#55595f", width=2)


CABLES = ["#2f6fd6", "#3a3d44", "#d9b44a", "#8c9096", "#2f6fd6", "#c85a3c", "#3a3d44"]

# 1. 설치 전: 꽉 찬 단자함 내부
img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)
vgrad(d, (0, 0, W, H), (196, 192, 184), (160, 156, 148))
d.rectangle((90, 80, 990, 1270), fill="#8d939b", outline="#5d636b", width=14)  # 함체
d.rectangle((130, 120, 950, 1230), fill="#52575f")
for row, y in enumerate(range(170, 1100, 150)):
    d.rectangle((160, y, 920, y + 90), fill="#2a2d33", outline="#6a6f77", width=3)  # 패치패널·장비
    ports(d, 190, y + 22, 15)
    for k in range(9):
        x = 205 + k * 80
        cable(d, (x, y + 70), (random.randint(150, 930), y + 150 + random.randint(0, 120)),
              random.choice(CABLES), w=random.randint(7, 11), sag=random.randint(40, 120))
for _ in range(25):  # 아래로 늘어진 배선 다발
    x = random.randint(170, 900)
    cable(d, (x, 1080), (random.randint(160, 920), 1225), random.choice(CABLES), w=8, sag=60)
grain(img).save(OUT / "1_before_cabinet.jpg", quality=88)

# 2. 설치 후: 벽 받침대 위 녹취서버
img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)
vgrad(d, (0, 0, W, H), (232, 226, 214), (205, 198, 186))
d.rectangle((0, 1180, W, H), fill="#b9ad98")  # 걸레받이
d.polygon([(300, 640), (780, 640), (780, 668), (300, 668)], fill="#8a8f96")  # 선반
for bx in (360, 700):
    d.polygon([(bx, 668), (bx + 22, 668), (bx + 22, 820), (bx, 668 + 20)], fill="#7a7f86")  # 브래킷
d.rectangle((350, 470, 730, 640), fill="#23262c", outline="#3d4249", width=4)  # 녹취서버
for i in range(4):
    d.ellipse((380 + i * 30, 600, 392 + i * 30, 612), fill=["#3ad16a", "#3ad16a", "#f2b233", "#3ad16a"][i])
d.rectangle((560, 590, 700, 615), fill="#15171b")
cable(d, (700, 640), (860, 1180), "#2f6fd6", w=10, sag=60)
cable(d, (680, 640), (820, 1180), "#3a3d44", w=10, sag=50)
d.rectangle((800, 1060, 1000, 1180), fill="#9aa0a7", outline="#6b7178", width=6)  # 아래 단자함 문
grain(img).save(OUT / "2_after_wall_server.jpg", quality=88)

# 3. 단자함 안 소형 미러링 스위치
img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)
vgrad(d, (0, 0, W, H), (88, 92, 99), (60, 63, 69))
d.rectangle((180, 520, 900, 760), fill="#2b2e34", outline="#70757d", width=6)  # 스위치
ports(d, 230, 620, 8, size=58, gap=18)
for i in range(8):
    d.ellipse((248 + i * 76, 575, 262 + i * 76, 589), fill="#3ad16a" if i % 3 else "#f2b233")
for i in range(5):
    x = 259 + i * 76
    cable(d, (x, 667), (x - 120 + i * 40, 1300), random.choice(CABLES), w=16, sag=30)
for i in range(6):
    cable(d, (random.randint(60, 1020), 0), (random.randint(60, 1020), 430), random.choice(CABLES), w=12, sag=70)
grain(img).save(OUT / "3_mirroring_switch.jpg", quality=88)

# 4. 기존 전화기 (교체 없음)
img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)
vgrad(d, (0, 0, W, 700), (226, 228, 230), (210, 212, 214))
vgrad(d, (0, 700, W, H), (166, 132, 100), (140, 108, 80))  # 책상
d.polygon([(250, 760), (830, 760), (900, 1150), (180, 1150)], fill="#2a2c31")  # 전화기 몸체
d.rectangle((430, 800, 650, 900), fill="#7f9aa8")  # 화면
for r in range(4):
    for c in range(3):
        x, y = 440 + c * 70, 930 + r * 50
        d.rounded_rectangle((x, y, x + 52, y + 36), 8, fill="#4a4d54")
d.rounded_rectangle((200, 700, 380, 1120), 60, fill="#24262b")  # 수화기
cable(d, (290, 1120), (120, 1300), "#24262b", w=10, sag=80)
grain(img).save(OUT / "4_existing_phone.jpg", quality=88)
print("saved", sorted(p.name for p in OUT.glob("*.jpg")))
