"""
B1 圖資轉換工具
  1. 讀取 B1 車格 WKT（Excel：WKT / 名稱 / 說明）→ 輸出 parking-b1.geojson
  2. 以 SVG 建築物外框 26 個頂點對應 WKT「結構牆1~26」做仿射擬合，
     將 B1 SVG 變形成與 B2 底圖相同的 imageBounds，輸出 B1-20260501-geo.svg
  3. 預設再以建築物四個邊角對齊 B2 外牆角點（SVG 與 WKT 同步套用）

用法：
  python tools/build_b1.py <B1停車格.xlsx> <B1原始.svg> [--keep-wkt]
    --keep-wkt：不做四角擬合，沿用 Excel 內的 WKT 座標
需要：openpyxl、numpy
"""
import json, math, os, re, sys
import numpy as np
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.dirname(HERE)

# 與 index.html 的 imageBounds 相同（B2 底圖範圍）
LNG_W, LNG_E = 120.34105, 120.34360
LAT_S, LAT_N = 22.62193, 22.62406
VB_W, VB_H = 1300, 1140

# B1 車道路網（B1 SVG 原始座標，車道中心線）：一圈環狀車道
NODES_SVG = {
    "P1": (148.8, 745.2),   # 西南（三多一路入口側）
    "P2": (148.8, 104.0),   # 西北
    "P3": (1118.7, 104.0),  # 東北
    "P4": (1118.7, 745.2),  # 東南（國泰路入口側）
}
EDGES = [("P1", "P2"), ("P2", "P3"), ("P3", "P4"), ("P4", "P1")]

# 四角擬合：B1 SVG 建築物主體四個邊角（西南、西北、東北、東南）
B1_CORNERS_SVG = [(105.42, 757.41), (105.42, 88.88), (1163.02, 88.88), (1163.02, 757.41)]
# 對應 parking.geojson（B2）的外牆角點：西側/北側/東側/南側牆面端點
B2_CORNERS = [(120.3411313255, 22.62264215293), (120.34158895444, 22.62401444329),
              (120.34358730345, 22.62334803743), (120.3431296745, 22.62197574707)]

# 不可作為導航點的區域
NON_NAV = {"非開放區域"}

# 原始 WKT 中與前一格座標重複的車格：以「前一格 + 相鄰格距」修正
DUPLICATE_FIX = {"60": ("58", "59"), "176": ("174", "175")}


def parse_wkt(wkt):
    nums = [float(x) for x in re.findall(r"-?\d+\.\d+", wkt)]
    return [[nums[i], nums[i + 1]] for i in range(0, len(nums), 2)]


def main(xlsx, svg_path, keep_wkt=False):
    rows = []
    for r in openpyxl.load_workbook(xlsx).active.iter_rows(min_row=2, values_only=True):
        wkt, name, note = r[:3]
        if wkt and name is not None:
            rows.append((str(wkt), str(name).strip(), note or ""))

    # --- 1. 仿射擬合：SVG 外框 → 經緯度 ---
    svg = open(svg_path, encoding="utf-8").read()
    pts = re.search(r'<polygon points="([^"]+)"', svg).group(1).split()
    S = np.array([[float(pts[i]), float(pts[i + 1])] for i in range(0, len(pts), 2)])
    if (S[0] == S[-1]).all(): S = S[:-1]  # 去除封閉多邊形的重複終點
    walls = {}
    for wkt, name, _ in rows:
        m = re.match(r"結構牆(\d+)$", name)
        if m: walls[int(m.group(1))] = parse_wkt(wkt)[0]
    G = np.array([walls[k] for k in sorted(walls)])
    assert len(S) == len(G), f"外框頂點數 {len(S)} 與結構牆數 {len(G)} 不符"
    A = np.hstack([S, np.ones((len(S), 1))])
    X, *_ = np.linalg.lstsq(A, G, rcond=None)  # [x y 1] @ X = [lng lat]（WKT 座標系）
    kx = 111320 * math.cos(math.radians((LAT_S + LAT_N) / 2))
    res = np.sqrt((((A @ X - G) * [kx, 110574]) ** 2).sum(1))
    print(f"SVG 與 WKT 仿射擬合誤差：最大 {res.max():.3f} m，平均 {res.mean():.3f} m")

    # --- 1b. 四角擬合：B1 建築物四個邊角對齊 B2 建築物外牆角點 ---
    # T: [lng lat 1](WKT) @ T = [lng lat](對齊 B2)；SVG 與 WKT 同步套用，維持兩者一致
    T = np.vstack([np.eye(2), [0, 0]])
    if not keep_wkt:
        src = np.array([np.array([x, y, 1]) @ X for x, y in B1_CORNERS_SVG])
        T, *_ = np.linalg.lstsq(np.hstack([src, np.ones((4, 1))]), np.array(B2_CORNERS), rcond=None)
        moved = [math.hypot((s[0] - d[0]) * kx, (s[1] - d[1]) * 110574) for s, d in zip(src, B2_CORNERS)]
        print("四角擬合位移（m）：", [round(m, 1) for m in moved])
    X = np.hstack([X, [[0], [0], [1]]]) @ T  # 合成：SVG → 對齊後經緯度

    def fit_geo(p):
        lng, lat = np.array([p[0], p[1], 1]) @ T
        return [round(float(lng), 11), round(float(lat), 11)]

    def svg_to_lnglat(x, y):
        lng, lat = np.array([x, y, 1]) @ X
        return [round(float(lng), 11), round(float(lat), 11)]

    # --- 2. 產生變形後 SVG（viewBox 對齊 B2 imageBounds）---
    sx = VB_W / (LNG_E - LNG_W); sy = -VB_H / (LAT_N - LAT_S)
    a, c = X[0, 0] * sx, X[0, 1] * sy
    b, d = X[1, 0] * sx, X[1, 1] * sy
    e, f = (X[2, 0] - LNG_W) * sx, (X[2, 1] - LAT_N) * sy
    body = re.sub(r"^.*?<svg[^>]*>", "", svg, flags=re.S)
    body = re.sub(r"</svg>\s*$", "", body)
    body = re.sub(r'<g id="a">\s*<rect[^>]*/>\s*</g>', "", body, count=1)  # 移除整張灰底
    out_svg = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {VB_H}" preserveAspectRatio="none">'
        f'<g transform="matrix({a:.8f} {c:.8f} {b:.8f} {d:.8f} {e:.6f} {f:.6f})">{body}</g></svg>'
    )
    open(os.path.join(OUT_DIR, "B1-20260501-geo.svg"), "w", encoding="utf-8").write(out_svg)

    # --- 3. 產生 GeoJSON ---
    nodes = {k: svg_to_lnglat(*v) for k, v in NODES_SVG.items()}

    def nearest_edge(p):
        best, bd = "", 1e9
        for u, v in EDGES:
            (x1, y1), (x2, y2) = nodes[u], nodes[v]
            dx, dy = x2 - x1, y2 - y1
            t = max(0, min(1, ((p[0] - x1) * dx + (p[1] - y1) * dy) / (dx * dx + dy * dy)))
            dd = math.hypot((x1 + t * dx - p[0]) * kx, (y1 + t * dy - p[1]) * 110574)
            if dd < bd: best, bd = u + v, dd
        return best

    geoms = {name: parse_wkt(wkt) for wkt, name, _ in rows}
    for bad, (prev2, prev1) in DUPLICATE_FIX.items():
        if geoms.get(bad) == geoms.get(prev1):
            p2, p1 = geoms[prev2], geoms[prev1]
            geoms[bad] = [[round(q[0] + (q[0] - r[0]), 11), round(q[1] + (q[1] - r[1]), 11)] for q, r in zip(p1, p2)]
            print(f"已修正重複座標車格 {bad}（依 {prev2}→{prev1} 格距外推）")
    geoms = {k: [fit_geo(p) for p in v] for k, v in geoms.items()}

    features = []
    for wkt, name, note in rows:
        coords = geoms[name]
        if wkt.startswith("POLYGON"):
            geom = {"type": "Polygon", "coordinates": [coords]}
            c0 = np.mean(coords[:-1], axis=0)
            road = "" if name in NON_NAV else nearest_edge(c0)
        else:
            geom = {"type": "LineString", "coordinates": coords}
            road = ""
        features.append({"type": "Feature",
                         "properties": {"name": name, "road_id": road, "description": note},
                         "geometry": geom})
    # 柱號：tools/b1_pillars.csv（由 SVG 柱號文字位置萃取，座標為 B1 原始 SVG）
    with open(os.path.join(HERE, "b1_pillars.csv"), encoding="utf-8") as fp:
        for line in fp.read().splitlines()[1:]:
            name, x, y = line.split(",")
            p = svg_to_lnglat(float(x), float(y))
            features.append({"type": "Feature",
                             "properties": {"name": name, "type": "pillar", "road_id": nearest_edge(p), "description": ""},
                             "geometry": {"type": "Point", "coordinates": p}})

    fc = {"type": "FeatureCollection",
          "road_network": {"nodes": nodes, "edges": [list(e) for e in EDGES]},
          "features": features}
    with open(os.path.join(OUT_DIR, "parking-b1.geojson"), "w", encoding="utf-8") as fp:
        json.dump(fc, fp, ensure_ascii=False)
    print(f"輸出 {len(features)} 筆圖徵、路網節點：{json.dumps(nodes)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], keep_wkt="--keep-wkt" in sys.argv[3:])
