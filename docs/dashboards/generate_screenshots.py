"""
Dashboard Screenshot Generator
Generates Grafana-style dashboard screenshots for portfolio using Pillow.
"""

from PIL import Image, ImageDraw, ImageFont
import math
import os

# ─── Constants ─────────────────────────────────────────────
W, H = 1440, 900
SCALE = 2  # Retina
W2, H2 = W * SCALE, H * SCALE

# Colors (Grafana dark theme)
BG = (17, 18, 23)
PANEL_BG = (24, 27, 31)
BORDER = (44, 45, 51)
TEXT = (216, 217, 218)
TEXT_DIM = (142, 142, 160)
TEXT_HEADER = (204, 204, 220)
BLUE = (110, 159, 255)
GREEN = (115, 191, 105)
RED = (242, 73, 92)
YELLOW = (255, 203, 71)
ORANGE = (255, 152, 48)
PURPLE = (184, 119, 217)
CYAN = (80, 198, 219)

OUT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)

def get_font(size):
    """Get a font, falling back to default if custom fonts unavailable."""
    for name in [
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFCompact.ttf",
    ]:
        try:
            return ImageFont.truetype(name, size * SCALE)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()

font_sm = get_font(11)
font_md = get_font(13)
font_lg = get_font(16)
font_xl = get_font(28)
font_stat = get_font(36)


def s(v):
    """Scale value for retina."""
    return int(v * SCALE)


def draw_panel(draw, x, y, w, h, title="", subtitle=""):
    """Draw a Grafana-style panel."""
    x1, y1 = s(x), s(y)
    x2, y2 = s(x + w), s(y + h)
    # Background
    draw.rounded_rectangle([x1, y1, x2, y2], radius=s(4), fill=PANEL_BG, outline=BORDER)
    # Header
    if title:
        draw.rectangle([x1, y1, x2, y1 + s(32)], fill=PANEL_BG)
        draw.line([x1, y1 + s(32), x2, y1 + s(32)], fill=BORDER, width=SCALE)
        draw.text((x1 + s(12), y1 + s(8)), title, fill=TEXT_HEADER, font=font_md)
        if subtitle:
            tw = draw.textlength(title, font=font_md)
            draw.text((x1 + s(12) + int(tw) + s(12), y1 + s(10)), subtitle, fill=TEXT_DIM, font=font_sm)
    return x1, y1 + s(32), x2, y2


def draw_stat_panel(draw, x, y, w, h, title, value, label, trend, trend_dir="up", color=BLUE):
    """Draw a stat panel."""
    px1, py1, px2, py2 = draw_panel(draw, x, y, w, h, title)
    cx = (px1 + px2) // 2
    cy = (py1 + py2) // 2 - s(8)
    # Value
    tw = draw.textlength(value, font=font_stat)
    draw.text((cx - int(tw) // 2, cy - s(20)), value, fill=color, font=font_stat)
    # Label
    tw2 = draw.textlength(label, font=font_sm)
    draw.text((cx - int(tw2) // 2, cy + s(30)), label, fill=TEXT_DIM, font=font_sm)
    # Trend
    trend_color = GREEN if trend_dir == "up" else RED if trend_dir == "down" else ORANGE
    tw3 = draw.textlength(trend, font=font_sm)
    draw.text((cx - int(tw3) // 2, cy + s(50)), trend, fill=trend_color, font=font_sm)


def draw_line_chart(draw, x, y, w, h, data, color=BLUE, fill_alpha=20, y_min=None, y_max=None):
    """Draw a simple line chart."""
    if not data:
        return
    x1, y1 = s(x), s(y)
    chart_w, chart_h = s(w), s(h)

    min_v = y_min if y_min is not None else min(d for d in data if d is not None)
    max_v = y_max if y_max is not None else max(d for d in data if d is not None)
    if max_v == min_v:
        max_v = min_v + 1

    points = []
    for i, d in enumerate(data):
        if d is None:
            continue
        px = x1 + int(i / (len(data) - 1) * chart_w)
        py = y1 + chart_h - int((d - min_v) / (max_v - min_v) * chart_h)
        points.append((px, py))

    if len(points) < 2:
        return

    # Fill area
    fill_color = (*color, fill_alpha)
    if len(points) >= 2:
        fill_points = points + [(points[-1][0], y1 + chart_h), (points[0][0], y1 + chart_h)]
        # Simple fill with slightly transparent color
        fill_solid = (color[0] // 8, color[1] // 8, color[2] // 8)
        draw.polygon(fill_points, fill=fill_solid)

    # Line
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=color, width=s(2))


def draw_bar_chart(draw, x, y, w, h, data, labels, colors_list, bar_width_ratio=0.6):
    """Draw a simple bar chart."""
    x1, y1 = s(x), s(y)
    chart_w, chart_h = s(w), s(h)
    n = len(data)
    if n == 0:
        return

    num_series = len(data)
    num_bars = len(data[0])
    group_w = chart_w // num_bars
    bar_w = int(group_w * bar_width_ratio / num_series)

    for series_idx, series in enumerate(data):
        max_v = max(max(s_data) for s_data in data)
        if max_v == 0:
            max_v = 1
        color = colors_list[series_idx % len(colors_list)]
        for i, v in enumerate(series):
            bx = x1 + i * group_w + series_idx * bar_w + (group_w - bar_w * num_series) // 2
            bar_h = int(v / max_v * chart_h * 0.9)
            by = y1 + chart_h - bar_h
            draw.rounded_rectangle([bx, by, bx + bar_w, y1 + chart_h], radius=s(2), fill=color)


def draw_badge(draw, x, y, text, color):
    """Draw a status badge."""
    bg_color = (color[0] // 6, color[1] // 6, color[2] // 6)
    tw = draw.textlength(text, font=font_sm)
    draw.rounded_rectangle([s(x), s(y), s(x) + int(tw) + s(16), s(y) + s(20)], radius=s(3), fill=bg_color)
    draw.text((s(x) + s(8), s(y) + s(3)), text, fill=color, font=font_sm)


def draw_table_row(draw, x, y, w, cols, values, statuses=None):
    """Draw a table row."""
    col_widths = [0.18, 0.22, 0.18, 0.18, 0.24]
    cx = s(x)
    for i, (val, cw) in enumerate(zip(values, col_widths)):
        cell_w = int(s(w) * cw)
        if statuses and i == len(values) - 1:
            badge_color = GREEN if val == "PASS" else ORANGE if val == "WARN" else RED
            draw_badge(draw, x + int(w * sum(col_widths[:i])), y, val, badge_color)
        else:
            draw.text((cx + s(8), s(y) + s(3)), str(val), fill=TEXT if i < 2 else TEXT_DIM, font=font_sm)
        cx += cell_w


def draw_funnel(draw, x, y, w, steps):
    """Draw a conversion funnel."""
    max_val = steps[0][1]
    for i, (label, value) in enumerate(steps):
        sy = s(y + i * 28)
        # Label
        draw.text((s(x), sy + s(4)), label, fill=TEXT_DIM, font=font_sm)
        # Bar background
        bar_x = s(x + 100)
        bar_w = s(w - 170)
        draw.rounded_rectangle([bar_x, sy + s(2), bar_x + bar_w, sy + s(22)],
                               radius=s(2), fill=(30, 33, 40))
        # Bar fill
        ratio = value / max_val
        fill_w = int(bar_w * ratio)
        if fill_w > 0:
            bar_color = (BLUE[0], BLUE[1], BLUE[2])
            draw.rounded_rectangle([bar_x, sy + s(2), bar_x + fill_w, sy + s(22)],
                                   radius=s(2), fill=(bar_color[0] // 3, bar_color[1] // 3, bar_color[2] // 3))
        # Value
        vtext = f"{value:,}"
        vtw = draw.textlength(vtext, font=font_sm)
        draw.text((s(x + w) - int(vtw), sy + s(4)), vtext, fill=TEXT, font=font_sm)


def draw_pipeline_row(draw, x, y, w, name, info, status_color, status_text):
    """Draw a pipeline status row."""
    row_y = s(y)
    draw.rounded_rectangle([s(x), row_y, s(x + w), row_y + s(32)],
                           radius=s(4), fill=(34, 37, 42))
    # Status dot
    dot_x, dot_y = s(x + 12), row_y + s(12)
    draw.ellipse([dot_x, dot_y, dot_x + s(8), dot_y + s(8)], fill=status_color)
    # Name
    draw.text((s(x + 28), row_y + s(8)), name, fill=TEXT, font=font_sm)
    # Info
    info_tw = draw.textlength(info, font=font_sm)
    draw.text((s(x + w) - int(info_tw) - s(8), row_y + s(8)), info, fill=TEXT_DIM, font=font_sm)


def draw_section_header(draw, x, y, text, icon=""):
    """Draw a section header."""
    draw.text((s(x), s(y)), f"{icon} {text}", fill=BLUE, font=font_lg)


# ═══════════════════════════════════════════════════════════
# Dashboard 1: Overview
# ═══════════════════════════════════════════════════════════
def generate_overview():
    img = Image.new("RGB", (W2, s(1050)), BG)
    draw = ImageDraw.Draw(img)

    # Top bar
    draw.rectangle([0, 0, W2, s(40)], fill=(26, 27, 31))
    draw.line([0, s(40), W2, s(40)], fill=BORDER, width=SCALE)
    draw.text((s(16), s(10)), "E-commerce Data Platform / Overview", fill=TEXT, font=font_lg)
    draw.text((W2 - s(160), s(12)), "🕐 Last 24 hours", fill=TEXT_DIM, font=font_sm)

    # Section: Key Metrics
    draw_section_header(draw, 12, 52, "Key Metrics", "📊")

    # Stat panels
    pw = 340
    draw_stat_panel(draw, 12, 78, pw, 108, "Events Ingested (24h)", "2.84M", "events processed", "▲ 12.3% vs yesterday", "up", BLUE)
    draw_stat_panel(draw, 12 + pw + 8, 78, pw, 108, "Pipeline Success Rate", "99.7%", "success / total", "▲ 0.2% vs 7d avg", "up", GREEN)
    draw_stat_panel(draw, 12 + (pw + 8) * 2, 78, pw, 108, "Data Freshness (SLA)", "4.2m", "avg latency (target: <30m)", "▼ 1.1m vs last week", "up", GREEN)
    draw_stat_panel(draw, 12 + (pw + 8) * 3, 78, pw, 108, "BigQuery Cost (Today)", "$12.40", "estimated scan cost", "▼ 31% after optimization", "up", YELLOW)

    # Section: Pipeline Performance
    draw_section_header(draw, 12, 200, "Pipeline Performance", "📈")
    half_w = 700

    # Throughput chart
    px1, py1, px2, py2 = draw_panel(draw, 12, 226, half_w, 230, "Events Throughput (RPS)", "event-collector → Pub/Sub")
    throughput_data = [320, 290, 180, 120, 85, 72, 68, 95, 180, 420, 680, 820, 950, 1100, 980, 870, 920, 1050, 1180, 1020, 780, 620, 480, 380]
    draw_line_chart(draw, 32, 270, half_w - 40, 170, throughput_data, BLUE)
    # Threshold line
    threshold_y = s(270) + s(170) - int(1000 / 1200 * s(170))
    draw.line([s(32), threshold_y, s(32 + half_w - 40), threshold_y], fill=(*RED, 128), width=SCALE)
    draw.text((s(half_w - 80), threshold_y - s(14)), "HPA: 1000 RPS", fill=RED, font=font_sm)
    # X labels
    for i in range(0, 24, 4):
        lx = s(32) + int(i / 23 * s(half_w - 40))
        draw.text((lx, s(446)), f"{i:02d}:00", fill=TEXT_DIM, font=font_sm)

    # Duration chart
    px1, py1, px2, py2 = draw_panel(draw, 12 + half_w + 8, 226, half_w, 230, "Pipeline Execution Duration", "seconds")
    batch_data = [[520, 498, 512, 504, 495, 510, 504]]
    draw_bar_chart(draw, 12 + half_w + 28, 270, half_w - 40, 170, batch_data, [], [BLUE])

    # Section: Data Quality & Business
    draw_section_header(draw, 12, 470, "Data Quality & Business Metrics", "🔍")

    # Quality table
    px1, py1, px2, py2 = draw_panel(draw, 12, 496, half_w, 280, "Data Quality Checks", "Last run: 2 min ago")
    # Table header
    header_y = 532
    headers = ["Check", "Table", "Value", "Threshold", "Status"]
    col_x = [32, 160, 310, 420, 560]
    for i, h in enumerate(headers):
        draw.text((s(col_x[i]), s(header_y)), h, fill=TEXT_DIM, font=font_sm)
    draw.line([s(24), s(header_y + 20), s(12 + half_w - 12), s(header_y + 20)], fill=BORDER, width=SCALE)

    # Table rows
    rows = [
        ("Freshness", "user_events", "4.2 min", "< 30 min", "PASS"),
        ("Freshness", "cdc_orders", "2.8 min", "< 15 min", "PASS"),
        ("Volume Z-Score", "user_events", "1.34", "< 2.0", "PASS"),
        ("Volume Z-Score", "cdc_orders", "1.89", "< 2.0", "WARN"),
        ("Null Rate", "user_events", "0.8%", "< 5%", "PASS"),
        ("Duplicate Rate", "user_events", "0.003%", "< 1%", "PASS"),
    ]
    for i, row in enumerate(rows):
        ry = header_y + 28 + i * 26
        for j, val in enumerate(row):
            if j == 4:
                badge_color = GREEN if val == "PASS" else ORANGE if val == "WARN" else RED
                bg = (badge_color[0] // 6, badge_color[1] // 6, badge_color[2] // 6)
                vtw = draw.textlength(val, font=font_sm)
                draw.rounded_rectangle([s(col_x[j]), s(ry), s(col_x[j]) + int(vtw) + s(14), s(ry + 18)],
                                       radius=s(3), fill=bg)
                draw.text((s(col_x[j]) + s(7), s(ry) + s(2)), val, fill=badge_color, font=font_sm)
            else:
                draw.text((s(col_x[j]), s(ry) + s(2)), val, fill=TEXT if j < 2 else TEXT_DIM, font=font_sm)

    # Funnel
    px1, py1, px2, py2 = draw_panel(draw, 12 + half_w + 8, 496, half_w, 280, "Conversion Funnel (7d)", "All Devices")
    funnel_steps = [
        ("Page View", 142380),
        ("Product View", 96818),
        ("Add to Cart", 44138),
        ("Checkout", 25629),
        ("Purchase", 17086),
    ]
    draw_funnel(draw, 12 + half_w + 24, 536, half_w - 32, funnel_steps)

    # Funnel KPIs
    kpi_y = 700
    kpis = [("12.0%", "Overall CVR", BLUE), ("66.7%", "Checkout→Purchase", GREEN), ("₩48,200", "Avg Order Value", ORANGE)]
    kpi_w = (half_w - 16) // 3
    for i, (val, label, color) in enumerate(kpis):
        kx = s(12 + half_w + 8 + i * kpi_w + kpi_w // 2)
        vtw = draw.textlength(val, font=font_lg)
        draw.text((kx - int(vtw) // 2, s(kpi_y)), val, fill=color, font=font_lg)
        ltw = draw.textlength(label, font=font_sm)
        draw.text((kx - int(ltw) // 2, s(kpi_y + 22)), label, fill=TEXT_DIM, font=font_sm)

    # Draw grid lines for aesthetics
    for y_pos in [s(196), s(464)]:
        draw.line([0, y_pos, W2, y_pos], fill=(BORDER[0], BORDER[1], BORDER[2]), width=1)

    img.save(os.path.join(OUT_DIR, "dashboard-overview.png"), "PNG", optimize=True)
    print("✅ dashboard-overview.png")
    return img


# ═══════════════════════════════════════════════════════════
# Dashboard 2: AI + Cost
# ═══════════════════════════════════════════════════════════
def generate_ai_cost():
    img = Image.new("RGB", (W2, s(950)), BG)
    draw = ImageDraw.Draw(img)

    # Top bar
    draw.rectangle([0, 0, W2, s(40)], fill=(26, 27, 31))
    draw.line([0, s(40), W2, s(40)], fill=BORDER, width=SCALE)
    draw.text((s(16), s(10)), "E-commerce Data Platform / AI & Cost", fill=TEXT, font=font_lg)

    half_w = 700

    # Section: AI Quality Agent & Pipeline
    draw_section_header(draw, 12, 52, "AI Quality Agent & Pipeline Status", "🤖")

    # Pipeline Status panel
    px1, py1, px2, py2 = draw_panel(draw, 12, 78, half_w, 260, "Pipeline Status", "Active Pipelines")
    pipelines = [
        ("Event Collector", "3/10 pods · CPU 42% · Healthy", GREEN),
        ("CDC Realtime", "1/1 pod · Buffer 23% · Streaming", GREEN),
        ("Batch ETL (Daily)", "Last: 03:42 KST · 8m 24s · Completed", GREEN),
        ("Beam/Dataflow", "2 workers · Backlog: 0 · Running", GREEN),
        ("Quality Agent", "CronJob · Next: 12:30 KST · Scheduled", YELLOW),
    ]
    for i, (name, info, status_color) in enumerate(pipelines):
        draw_pipeline_row(draw, 24, 116 + i * 40, half_w - 24, name, info, status_color, "")

    # GenAI Report panel
    px1, py1, px2, py2 = draw_panel(draw, 12 + half_w + 8, 78, half_w, 260, "GenAI Quality Report", "Gemini 2.0 Flash")
    # AI tag
    draw.rounded_rectangle([s(half_w + 570), s(82), s(half_w + 700), s(98)],
                           radius=s(3), fill=(PURPLE[0] // 6, PURPLE[1] // 6, PURPLE[2] // 6))
    draw.text((s(half_w + 578), s(84)), "Gemini 2.0", fill=PURPLE, font=font_sm)

    # AI Report content
    report_x = 12 + half_w + 24
    report_y = 118
    # Border accent
    draw.rectangle([s(report_x - 4), s(report_y), s(report_x - 1), s(report_y + 200)], fill=PURPLE)
    draw.rounded_rectangle([s(report_x), s(report_y), s(report_x + half_w - 40), s(report_y + 200)],
                           radius=s(4), fill=(30, 32, 40))

    draw.text((s(report_x + 12), s(report_y + 8)), "🤖 AI Analysis Summary", fill=PURPLE, font=font_md)
    draw.text((s(report_x + 12), s(report_y + 32)), "cdc_orders 볼륨 경고 (z-score: 1.89)", fill=TEXT, font=font_sm)
    draw.text((s(report_x + 12), s(report_y + 54)), "주문량이 14일 평균 대비 약 32% 증가.", fill=TEXT_DIM, font=font_sm)
    draw.text((s(report_x + 12), s(report_y + 72)), "프로모션 이벤트에 따른 정상적 증가로 판단.", fill=TEXT_DIM, font=font_sm)

    draw.text((s(report_x + 12), s(report_y + 100)), "💡 권장 조치:", fill=YELLOW, font=font_md)
    actions = [
        "• Volume threshold z-score 3.0 상향 조정",
        "• CDC 버퍼 크기 100 → 200 증설",
        "• Streaming Insert quota 모니터링 강화",
    ]
    for i, action in enumerate(actions):
        draw.text((s(report_x + 18), s(report_y + 124 + i * 20)), action, fill=TEXT_DIM, font=font_sm)

    draw.text((s(report_x + 12), s(report_y + 180)), "SLA 위반 가능성: 낮음 ✅", fill=GREEN, font=font_sm)

    # Section: Cost & Scaling
    draw_section_header(draw, 12, 352, "Cost Optimization & Auto-Scaling", "💰")

    # Cost chart
    px1, py1, px2, py2 = draw_panel(draw, 12, 378, half_w, 260, "BigQuery Daily Cost Trend", "Scan cost (on-demand)")
    before_data = [18.2, 19.1, 17.8, 20.3, 22.1, 19.5, 18.8, None, None, None, None, None, None, None]
    after_data = [None, None, None, None, None, None, None, 14.2, 13.5, 12.8, 13.1, 12.9, 12.6, 12.4]
    draw_line_chart(draw, 32, 420, half_w - 40, 200, [v for v in before_data if v is not None], RED, 15, 10, 24)
    # Draw after data shifted
    valid_after = [(i, v) for i, v in enumerate(after_data) if v is not None]
    if valid_after:
        x_start = 32
        chart_w = half_w - 40
        chart_h = 200
        points = []
        for i, v in valid_after:
            px = s(x_start) + int(i / 13 * s(chart_w))
            py = s(420) + s(chart_h) - int((v - 10) / 14 * s(chart_h))
            points.append((px, py))
        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=GREEN, width=s(2))
    # Annotation
    mid_x = s(32) + int(6.5 / 13 * s(half_w - 40))
    draw.line([mid_x, s(420), mid_x, s(620)], fill=(*YELLOW, 80), width=SCALE)
    draw.text((mid_x + s(4), s(425)), "Optimization", fill=YELLOW, font=font_sm)
    draw.text((mid_x + s(4), s(440)), "Applied", fill=YELLOW, font=font_sm)
    # Labels
    draw.text((s(50), s(430)), "$19.1/day avg", fill=RED, font=font_sm)
    draw.text((s(half_w - 130), s(600)), "$12.4/day avg", fill=GREEN, font=font_sm)
    # Cost saving badge
    draw.rounded_rectangle([s(half_w - 160), s(555), s(half_w - 50), s(578)],
                           radius=s(4), fill=(GREEN[0] // 5, GREEN[1] // 5, GREEN[2] // 5))
    draw.text((s(half_w - 152), s(558)), "▼ 31% savings", fill=GREEN, font=font_md)

    # HPA chart
    px1, py1, px2, py2 = draw_panel(draw, 12 + half_w + 8, 378, half_w, 260, "HPA Pod Auto-Scaling", "event-collector replicas")
    hpa_data = [2, 2, 2, 2, 2, 2, 2, 2, 3, 4, 5, 6, 7, 8, 7, 6, 7, 8, 9, 7, 5, 4, 3, 2]
    draw_line_chart(draw, 12 + half_w + 28, 420, half_w - 40, 200, hpa_data, PURPLE, 12, 0, 12)
    # Min/Max lines
    min_y = s(420) + s(200) - int(2 / 12 * s(200))
    max_y = s(420) + s(200) - int(10 / 12 * s(200))
    chart_start = s(12 + half_w + 28)
    chart_end = s(12 + half_w + 28 + half_w - 40)
    draw.line([chart_start, min_y, chart_end, min_y], fill=(*GREEN, 60), width=SCALE)
    draw.line([chart_start, max_y, chart_end, max_y], fill=(*RED, 60), width=SCALE)
    draw.text((chart_end - s(50), min_y + s(2)), "Min: 2", fill=GREEN, font=font_sm)
    draw.text((chart_end - s(54), max_y - s(16)), "Max: 10", fill=RED, font=font_sm)

    # Section: User & CDC
    draw_section_header(draw, 12, 650, "User Analytics & CDC Monitoring", "👥")

    # DAU chart
    px1, py1, px2, py2 = draw_panel(draw, 12, 676, half_w, 260, "Daily Active Users (30d)", "staging.user_events")
    dau_data = [12400, 13100, 12800, 14200, 15600, 16800, 17200, 13500, 14100, 13800,
                15000, 16200, 17100, 17800, 14200, 14800, 14500, 15800, 17000, 18200,
                18800, 15100, 15600, 15200, 16500, 17800, 19100, 19800, 16200, 16800]
    draw_line_chart(draw, 32, 716, half_w - 40, 200, dau_data, CYAN, 12, 10000, 22000)

    # CDC Lag chart
    px1, py1, px2, py2 = draw_panel(draw, 12 + half_w + 8, 676, half_w, 260, "CDC Replication Lag", "PostgreSQL → BigQuery (seconds)")
    lag_data = [1.2, 1.1, 0.8, 0.6, 0.5, 0.4, 0.5, 0.8, 1.5, 2.2, 3.1, 3.8, 4.2, 4.8, 3.9, 3.2, 3.5, 4.1, 4.5, 3.8, 2.9, 2.1, 1.6, 1.3]
    draw_line_chart(draw, 12 + half_w + 28, 716, half_w - 40, 200, lag_data, ORANGE, 12, 0, 12)
    # SLA line
    sla_y = s(716) + s(200) - int(10 / 12 * s(200))
    lag_start = s(12 + half_w + 28)
    lag_end = s(12 + half_w + 28 + half_w - 40)
    draw.line([lag_start, sla_y, lag_end, sla_y], fill=(*RED, 80), width=SCALE)
    draw.text((lag_end - s(70), sla_y - s(16)), "SLA: 10s", fill=RED, font=font_sm)

    img.save(os.path.join(OUT_DIR, "dashboard-ai-cost.png"), "PNG", optimize=True)
    print("✅ dashboard-ai-cost.png")
    return img


# ═══════════════════════════════════════════════════════════
# Individual Panels
# ═══════════════════════════════════════════════════════════
def generate_hpa_panel():
    """Generate standalone HPA scaling panel."""
    pw, ph = 720, 300
    img = Image.new("RGB", (s(pw), s(ph)), BG)
    draw = ImageDraw.Draw(img)

    draw_panel(draw, 4, 4, pw - 8, ph - 8, "HPA Pod Auto-Scaling", "event-collector replicas (2~10)")
    hpa_data = [2, 2, 2, 2, 2, 2, 2, 2, 3, 4, 5, 6, 7, 8, 7, 6, 7, 8, 9, 7, 5, 4, 3, 2]
    draw_line_chart(draw, 20, 44, pw - 40, 240, hpa_data, PURPLE, 12, 0, 12)
    # Min/Max lines
    chart_end = s(pw - 20)
    min_y = s(44 + 240) - int(2 / 12 * s(240))
    max_y = s(44 + 240) - int(10 / 12 * s(240))
    draw.line([s(20), min_y, chart_end, min_y], fill=(*GREEN, 60), width=SCALE)
    draw.line([s(20), max_y, chart_end, max_y], fill=(*RED, 60), width=SCALE)
    draw.text((chart_end - s(50), min_y + s(4)), "Min: 2", fill=GREEN, font=font_sm)
    draw.text((chart_end - s(54), max_y - s(16)), "Max: 10", fill=RED, font=font_sm)
    # Time labels
    for i in range(0, 24, 4):
        lx = s(20) + int(i / 23 * s(pw - 40))
        draw.text((lx, s(ph - 18)), f"{i:02d}:00", fill=TEXT_DIM, font=font_sm)

    img.save(os.path.join(OUT_DIR, "dashboard-hpa-scaling.png"), "PNG", optimize=True)
    print("✅ dashboard-hpa-scaling.png")


def generate_cost_panel():
    """Generate standalone cost optimization panel."""
    pw, ph = 720, 300
    img = Image.new("RGB", (s(pw), s(ph)), BG)
    draw = ImageDraw.Draw(img)

    draw_panel(draw, 4, 4, pw - 8, ph - 8, "BigQuery Daily Cost Trend", "Scan cost (on-demand pricing)")

    # Before data
    before = [18.2, 19.1, 17.8, 20.3, 22.1, 19.5, 18.8]
    before_points = []
    for i, v in enumerate(before):
        px = s(20) + int(i / 13 * s(pw - 40))
        py = s(44 + 240) - int((v - 8) / 16 * s(240))
        before_points.append((px, py))
    for i in range(len(before_points) - 1):
        draw.line([before_points[i], before_points[i + 1]], fill=RED, width=s(2))
    for p in before_points:
        draw.ellipse([p[0] - s(3), p[1] - s(3), p[0] + s(3), p[1] + s(3)], fill=RED)

    # After data
    after = [14.2, 13.5, 12.8, 13.1, 12.9, 12.6, 12.4]
    after_points = []
    for i, v in enumerate(after):
        px = s(20) + int((i + 7) / 13 * s(pw - 40))
        py = s(44 + 240) - int((v - 8) / 16 * s(240))
        after_points.append((px, py))
    for i in range(len(after_points) - 1):
        draw.line([after_points[i], after_points[i + 1]], fill=GREEN, width=s(2))
    for p in after_points:
        draw.ellipse([p[0] - s(3), p[1] - s(3), p[0] + s(3), p[1] + s(3)], fill=GREEN)

    # Annotation line
    mid_x = s(20) + int(6.5 / 13 * s(pw - 40))
    draw.line([mid_x, s(44), mid_x, s(284)], fill=YELLOW, width=SCALE)
    draw.text((mid_x + s(6), s(50)), "SQL Optimizer", fill=YELLOW, font=font_sm)
    draw.text((mid_x + s(6), s(66)), "Applied", fill=YELLOW, font=font_sm)

    # Labels
    draw.text((s(30), s(55)), "Before: $19.1/day avg", fill=RED, font=font_sm)
    draw.text((s(pw - 200), s(250)), "After: $12.4/day avg", fill=GREEN, font=font_sm)

    # Savings badge
    draw.rounded_rectangle([s(pw // 2 - 80), s(ph - 50), s(pw // 2 + 80), s(ph - 24)],
                           radius=s(4), fill=(GREEN[0] // 5, GREEN[1] // 5, GREEN[2] // 5))
    draw.text((s(pw // 2 - 68), s(ph - 46)), "▼ 31% cost savings", fill=GREEN, font=font_md)

    img.save(os.path.join(OUT_DIR, "dashboard-cost-optimization.png"), "PNG", optimize=True)
    print("✅ dashboard-cost-optimization.png")


if __name__ == "__main__":
    print("🎨 Generating dashboard screenshots...\n")
    generate_overview()
    generate_ai_cost()
    generate_hpa_panel()
    generate_cost_panel()
    print(f"\n🎉 All screenshots saved to: {OUT_DIR}")
