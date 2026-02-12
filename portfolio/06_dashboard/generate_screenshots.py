"""
QuickPay Dashboard Screenshot Generator

Pillow로 대시보드 스크린샷을 생성합니다.
Chart.js 기반 HTML 대시보드의 주요 섹션을 시각화합니다.
"""

from PIL import Image, ImageDraw, ImageFont
import os
import math

# ─── Configuration ──────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

WIDTH = 1400
BG = "#0F1117"
CARD_BG = "#1A1C23"
BORDER = "#2D2F36"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#9CA3AF"
BLUE = "#3B82F6"
PURPLE = "#8B5CF6"
PINK = "#EC4899"
GREEN = "#22C55E"
YELLOW = "#F59E0B"
RED = "#EF4444"
GRAY = "#6B7280"


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def try_font(size):
    for name in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


font_xl = try_font(28)
font_lg = try_font(20)
font_md = try_font(14)
font_sm = try_font(11)
font_xs = try_font(10)
font_title = try_font(22)


def draw_rounded_rect(draw, xy, fill, radius=12, outline=None):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline)


def draw_text_c(draw, xy, text, fill, font, anchor="lt"):
    draw.text(xy, text, fill=hex_to_rgb(fill), font=font, anchor=anchor)


# ─── Screenshot 1: KPI Overview + Funnel ────────────────────
def generate_kpi_funnel():
    img = Image.new("RGB", (WIDTH, 520), hex_to_rgb(BG))
    d = ImageDraw.Draw(img)

    # Header
    draw_text_c(d, (24, 20), "QuickPay", BLUE, font_title)
    draw_text_c(d, (155, 20), "DataOps Dashboard", TEXT_PRIMARY, font_title)
    draw_text_c(d, (24, 50), "2024-12-15 (Sun) · Last updated 02:15 KST", TEXT_SECONDARY, font_sm)

    # Status
    d.ellipse([1280, 24, 1288, 32], fill=hex_to_rgb(GREEN))
    draw_text_c(d, (1294, 22), "Pipeline Healthy", TEXT_SECONDARY, font_sm)
    draw_text_c(d, (1180, 40), "Quality Score: 98.7%", GREEN, font_sm)

    # KPI Cards
    kpis = [
        ("DAU", "1.24M", "▲ 3.2%", GREEN),
        ("NET REVENUE", "₩4.8B", "▲ 7.1%", GREEN),
        ("ARPPU", "₩12,400", "▼ 1.3%", RED),
        ("PAYMENT CVR", "68.4%", "▲ 2.1%", GREEN),
        ("D7 RETENTION", "42.3%", "▲ 0.8%", GREEN),
    ]
    card_w = (WIDTH - 24*2 - 16*4) // 5
    for i, (label, value, change, color) in enumerate(kpis):
        x = 24 + i * (card_w + 16)
        y = 80
        draw_rounded_rect(d, (x, y, x+card_w, y+110), hex_to_rgb(CARD_BG), outline=hex_to_rgb(BORDER))
        draw_text_c(d, (x+16, y+16), label, TEXT_SECONDARY, font_xs)
        draw_text_c(d, (x+16, y+38), value, TEXT_PRIMARY, font_xl)
        draw_text_c(d, (x+16, y+78), change + " vs yesterday", color, font_xs)

    # Payment Funnel
    draw_rounded_rect(d, (24, 210, WIDTH-24, 500), hex_to_rgb(CARD_BG), outline=hex_to_rgb(BORDER))
    draw_text_c(d, (44, 226), "💳 결제 퍼널 전환율", TEXT_PRIMARY, font_lg)
    d.rounded_rectangle((270, 228, 340, 244), radius=4, fill=hex_to_rgb("#3B82F620"))
    draw_text_c(d, (276, 230), "REAL-TIME", BLUE, font_xs)

    funnel_data = [
        ("결제 화면 진입", "524,300", "100%", BLUE),
        ("결제 수단 선택", "418,200", "79.8%", PURPLE),
        ("결제 요청", "387,600", "73.9%", PINK),
        ("결제 완료", "358,500", "68.4%", GREEN),
    ]
    step_w = 280
    start_x = 80
    for i, (label, value, pct, color) in enumerate(funnel_data):
        x = start_x + i * (step_w + 40)
        y = 290
        bg_color = tuple(c // 8 for c in hex_to_rgb(color))
        bg_color = tuple(min(c + 20, 255) for c in bg_color)
        draw_rounded_rect(d, (x, y, x+step_w, y+160), bg_color, radius=8)
        draw_text_c(d, (x + step_w//2, y+20), label, TEXT_SECONDARY, font_sm, anchor="mt")
        draw_text_c(d, (x + step_w//2, y+60), value, TEXT_PRIMARY, font_xl, anchor="mt")
        draw_text_c(d, (x + step_w//2, y+105), pct, color, font_md, anchor="mt")

        # Arrow
        if i < 3:
            ax = x + step_w + 8
            d.text((ax, y+75), "→", fill=hex_to_rgb(GRAY), font=font_lg)

    path = os.path.join(OUTPUT_DIR, "01_kpi_funnel.png")
    img.save(path, "PNG")
    print(f"✅ {path}")


# ─── Screenshot 2: Revenue + DAU Charts ─────────────────────
def generate_revenue_dau():
    img = Image.new("RGB", (WIDTH, 400), hex_to_rgb(BG))
    d = ImageDraw.Draw(img)

    # Revenue Chart (Left)
    draw_rounded_rect(d, (24, 16, 690, 384), hex_to_rgb(CARD_BG), outline=hex_to_rgb(BORDER))
    draw_text_c(d, (44, 32), "📈 일별 매출 추이 (Net Revenue)", TEXT_PRIMARY, font_md)
    d.rounded_rectangle((290, 32, 340, 46), radius=4, fill=hex_to_rgb("#F59E0B20"))
    draw_text_c(d, (296, 34), "7D MA", YELLOW, font_xs)

    # Bar chart simulation
    revenue = [41.2, 43.8, 39.5, 44.1, 46.3, 52.8, 48.2, 42.1, 45.6, 47.3, 44.8, 46.2, 48.5, 48.0]
    ma7 = [None]*6 + [45.1, 45.3, 45.5, 46.1, 46.7, 46.4, 46.2, 46.1]
    max_v = 55
    chart_x, chart_y, chart_w, chart_h = 60, 70, 600, 280
    bar_w = chart_w // len(revenue) - 4

    for i, v in enumerate(revenue):
        x = chart_x + i * (bar_w + 4)
        h = int((v / max_v) * chart_h)
        y = chart_y + chart_h - h
        d.rounded_rectangle((x, y, x+bar_w, chart_y+chart_h), radius=3,
                           fill=hex_to_rgb(BLUE) + (128,))
        if i % 3 == 0:
            draw_text_c(d, (x, chart_y+chart_h+6), f"12/{2+i:02d}", TEXT_SECONDARY, font_xs)

    # MA line
    ma_points = []
    for i, v in enumerate(ma7):
        if v is not None:
            x = chart_x + i * (bar_w + 4) + bar_w // 2
            y = chart_y + chart_h - int((v / max_v) * chart_h)
            ma_points.append((x, y))
    if len(ma_points) > 1:
        d.line(ma_points, fill=hex_to_rgb(YELLOW), width=2)

    # DAU Chart (Right)
    draw_rounded_rect(d, (710, 16, WIDTH-24, 384), hex_to_rgb(CARD_BG), outline=hex_to_rgb(BORDER))
    draw_text_c(d, (730, 32), "👥 DAU / WAU / MAU 추이", TEXT_PRIMARY, font_md)

    dau = [112, 118, 115, 121, 119, 132, 128, 114, 120, 122, 118, 121, 124, 124]
    max_dau = 140
    cx, cy, cw, ch = 740, 70, 620, 280

    # DAU area fill
    dau_points = []
    for i, v in enumerate(dau):
        x = cx + int(i / (len(dau)-1) * cw)
        y = cy + ch - int((v / max_dau) * ch)
        dau_points.append((x, y))

    fill_points = dau_points + [(cx+cw, cy+ch), (cx, cy+ch)]
    d.polygon(fill_points, fill=hex_to_rgb(BLUE)[:3] + (30,))
    if len(dau_points) > 1:
        d.line(dau_points, fill=hex_to_rgb(BLUE), width=2)
        for p in dau_points:
            d.ellipse((p[0]-3, p[1]-3, p[0]+3, p[1]+3), fill=hex_to_rgb(BLUE))

    # Legend
    d.rectangle((740, 360, 750, 366), fill=hex_to_rgb(BLUE))
    draw_text_c(d, (756, 358), "DAU", TEXT_SECONDARY, font_xs)
    d.rectangle((800, 360, 810, 366), fill=hex_to_rgb(PURPLE))
    draw_text_c(d, (816, 358), "WAU", TEXT_SECONDARY, font_xs)
    d.rectangle((860, 360, 870, 366), fill=hex_to_rgb(GRAY))
    draw_text_c(d, (876, 358), "MAU", TEXT_SECONDARY, font_xs)

    path = os.path.join(OUTPUT_DIR, "02_revenue_dau.png")
    img.save(path, "PNG")
    print(f"✅ {path}")


# ─── Screenshot 3: Retention + Payment Methods ──────────────
def generate_retention_methods():
    img = Image.new("RGB", (WIDTH, 400), hex_to_rgb(BG))
    d = ImageDraw.Draw(img)

    # Retention Chart (Left)
    draw_rounded_rect(d, (24, 16, 690, 384), hex_to_rgb(CARD_BG), outline=hex_to_rgb(BORDER))
    draw_text_c(d, (44, 32), "🔄 코호트 리텐션 (Week of Dec 8)", TEXT_PRIMARY, font_md)

    retention = [100, 68, 55, 42.3, 31.5, 21.3]
    labels = ["D0", "D1", "D3", "D7", "D14", "D30"]
    cx, cy, cw, ch = 60, 70, 600, 270

    # Grid lines
    for pct in [0, 25, 50, 75, 100]:
        y = cy + ch - int((pct / 110) * ch)
        d.line([(cx, y), (cx+cw, y)], fill=hex_to_rgb(BORDER), width=1)
        draw_text_c(d, (cx-30, y-6), f"{pct}%", TEXT_SECONDARY, font_xs)

    # Line + area
    points = []
    for i, v in enumerate(retention):
        x = cx + int(i / (len(retention)-1) * cw)
        y = cy + ch - int((v / 110) * ch)
        points.append((x, y))

    fill_pts = points + [(cx+cw, cy+ch), (cx, cy+ch)]
    d.polygon(fill_pts, fill=hex_to_rgb(BLUE)[:3] + (25,))
    d.line(points, fill=hex_to_rgb(BLUE), width=2)
    for i, (px, py) in enumerate(points):
        d.ellipse((px-5, py-5, px+5, py+5), fill=hex_to_rgb(BLUE))
        draw_text_c(d, (px, py-16), f"{retention[i]}%", BLUE, font_xs, anchor="mt")
        draw_text_c(d, (px, cy+ch+8), labels[i], TEXT_SECONDARY, font_xs, anchor="mt")

    # Payment Method Chart (Right) — Donut
    draw_rounded_rect(d, (710, 16, WIDTH-24, 384), hex_to_rgb(CARD_BG), outline=hex_to_rgb(BORDER))
    draw_text_c(d, (730, 32), "💰 결제 수단 비중", TEXT_PRIMARY, font_md)

    methods = [
        ("QuickPay 잔액", 42, BLUE),
        ("신용카드", 28, PURPLE),
        ("체크카드", 15, PINK),
        ("계좌이체", 10, GREEN),
        ("가상계좌", 5, GRAY),
    ]

    center_x, center_y, radius = 880, 210, 100
    inner_r = 60
    start_angle = -90
    for name, pct, color in methods:
        extent = pct / 100 * 360
        d.pieslice(
            (center_x-radius, center_y-radius, center_x+radius, center_y+radius),
            start_angle, start_angle + extent,
            fill=hex_to_rgb(color)
        )
        start_angle += extent
    d.ellipse(
        (center_x-inner_r, center_y-inner_r, center_x+inner_r, center_y+inner_r),
        fill=hex_to_rgb(CARD_BG)
    )

    # Legend
    legend_x, legend_y = 1020, 100
    for name, pct, color in methods:
        d.rectangle((legend_x, legend_y, legend_x+10, legend_y+10), fill=hex_to_rgb(color))
        draw_text_c(d, (legend_x+16, legend_y-1), f"{name} ({pct}%)", TEXT_SECONDARY, font_sm)
        legend_y += 24

    path = os.path.join(OUTPUT_DIR, "03_retention_payment.png")
    img.save(path, "PNG")
    print(f"✅ {path}")


# ─── Screenshot 4: Data Quality + Volume Monitoring ─────────
def generate_quality_monitoring():
    img = Image.new("RGB", (WIDTH, 480), hex_to_rgb(BG))
    d = ImageDraw.Draw(img)

    # Data Quality Panel
    draw_rounded_rect(d, (24, 16, WIDTH-24, 180), hex_to_rgb(CARD_BG), outline=hex_to_rgb(BORDER))
    draw_text_c(d, (44, 32), "🛡️ 데이터 품질 모니터링", TEXT_PRIMARY, font_md)
    d.rounded_rectangle((255, 32, 325, 48), radius=4, fill=hex_to_rgb("#22C55E20"))
    draw_text_c(d, (261, 34), "ALL PASS", GREEN, font_xs)

    quality_items = [
        ("Completeness", "99.8%", 0.998, GREEN),
        ("Uniqueness", "100%", 1.0, GREEN),
        ("Consistency", "99.2%", 0.992, GREEN),
        ("Freshness", "< 5min", 0.95, GREEN),
    ]
    item_w = (WIDTH - 48 - 36) // 4
    for i, (label, value, ratio, color) in enumerate(quality_items):
        x = 36 + i * (item_w + 12)
        y = 70
        draw_rounded_rect(d, (x, y, x+item_w, y+90), hex_to_rgb(BG), radius=8)
        draw_text_c(d, (x + item_w//2, y+12), label, TEXT_SECONDARY, font_xs, anchor="mt")
        draw_text_c(d, (x + item_w//2, y+35), value, color, font_lg, anchor="mt")
        # Progress bar
        bar_x, bar_y = x+16, y+70
        bar_w = item_w - 32
        d.rounded_rectangle((bar_x, bar_y, bar_x+bar_w, bar_y+4), radius=2, fill=hex_to_rgb(BORDER))
        d.rounded_rectangle((bar_x, bar_y, bar_x+int(bar_w*ratio), bar_y+4), radius=2, fill=hex_to_rgb(color))

    # Volume Chart
    draw_rounded_rect(d, (24, 200, WIDTH-24, 464), hex_to_rgb(CARD_BG), outline=hex_to_rgb(BORDER))
    draw_text_c(d, (44, 216), "🔍 이벤트 볼륨 & 이상 감지 (24h)", TEXT_PRIMARY, font_md)

    actual = [11,7,5,3,4,14,43,80,93,86,74,83,90,85,76,70,83,92,96,86,70,53,36,21]
    upper = [int(v*1.3) for v in [12,8,5,3,4,15,45,82,95,88,76,85,92,87,78,72,85,94,98,88,72,55,38,22]]
    lower = [int(v*0.7) for v in [12,8,5,3,4,15,45,82,95,88,76,85,92,87,78,72,85,94,98,88,72,55,38,22]]
    max_vol = 130
    cx, cy, cw, ch = 60, 250, WIDTH-120, 190

    def vol_point(i, v):
        x = cx + int(i / 23 * cw)
        y = cy + ch - int((v / max_vol) * ch)
        return (x, y)

    # Upper/lower band fill
    band_pts = [vol_point(i, upper[i]) for i in range(24)]
    band_pts += [vol_point(i, lower[i]) for i in range(23, -1, -1)]
    d.polygon(band_pts, fill=hex_to_rgb(GREEN)[:3] + (15,))

    # Upper line
    upper_pts = [vol_point(i, upper[i]) for i in range(24)]
    d.line(upper_pts, fill=hex_to_rgb(GREEN)[:3] + (60,), width=1)

    # Lower line
    lower_pts = [vol_point(i, lower[i]) for i in range(24)]
    d.line(lower_pts, fill=hex_to_rgb(GREEN)[:3] + (60,), width=1)

    # Actual line
    actual_pts = [vol_point(i, actual[i]) for i in range(24)]
    d.line(actual_pts, fill=hex_to_rgb(BLUE), width=2)
    for p in actual_pts[::3]:
        d.ellipse((p[0]-2, p[1]-2, p[0]+2, p[1]+2), fill=hex_to_rgb(BLUE))

    # X labels
    for i in range(0, 24, 3):
        x = cx + int(i / 23 * cw)
        draw_text_c(d, (x, cy+ch+6), f"{i:02d}:00", TEXT_SECONDARY, font_xs, anchor="mt")

    # Legend
    d.rectangle((cx, cy-20, cx+12, cy-16), fill=hex_to_rgb(BLUE))
    draw_text_c(d, (cx+18, cy-22), "실제 볼륨", TEXT_SECONDARY, font_xs)
    d.rectangle((cx+100, cy-20, cx+112, cy-16), fill=hex_to_rgb(GREEN)[:3] + (60,))
    draw_text_c(d, (cx+118, cy-22), "정상 범위", TEXT_SECONDARY, font_xs)

    path = os.path.join(OUTPUT_DIR, "04_quality_monitoring.png")
    img.save(path, "PNG")
    print(f"✅ {path}")


# ─── Generate All ──────────────────────────────────────────
if __name__ == "__main__":
    print("🎨 QuickPay Dashboard Screenshots 생성 중...")
    generate_kpi_funnel()
    generate_revenue_dau()
    generate_retention_methods()
    generate_quality_monitoring()
    print(f"\n✅ 모든 스크린샷 생성 완료: {OUTPUT_DIR}")
