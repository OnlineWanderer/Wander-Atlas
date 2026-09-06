from pathlib import Path
import xml.etree.ElementTree as ET
import json, math, re

GPX_DIR = Path("gpx")
OUT_DIR = Path("routes")
INFO_FILE = Path("route-info.json")
OUT_DIR.mkdir(exist_ok=True)

def local(tag):
    return tag.split("}")[-1]

def safe_slug(name):
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-").lower()
    return s or "route"

def haversine(a, b):
    R = 6371000
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2-lat1, lon2-lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(h))

info = {}
if INFO_FILE.exists():
    try:
        info = json.loads(INFO_FILE.read_text(encoding="utf-8"))
    except Exception:
        info = {}

manifest = []

for gpx in sorted(GPX_DIR.glob("*.gpx")):
    root = ET.parse(gpx).getroot()
    points, elevations = [], []
    name, date = gpx.stem, ""

    for el in root.iter():
        if local(el.tag) == "name" and el.text and el.text.strip():
            name = el.text.strip()
            break

    for pt in root.iter():
        if local(pt.tag) != "trkpt":
            continue
        lat, lon = float(pt.attrib["lat"]), float(pt.attrib["lon"])
        ele, time = None, None
        for child in pt:
            if local(child.tag) == "ele" and child.text:
                try: ele = float(child.text)
                except: pass
            elif local(child.tag) == "time" and child.text:
                time = child.text
        points.append((lat, lon))
        elevations.append(ele)
        if not date and time:
            date = time[:10]

    if len(points) < 2:
        continue

    distance_m = sum(haversine(points[i-1], points[i]) for i in range(1, len(points)))
    ascent, prev = 0.0, None
    for ele in elevations:
        if ele is None: continue
        if prev is not None and ele > prev: ascent += ele-prev
        prev = ele

    slug = safe_slug(gpx.stem)
    out_name = slug + ".geojson"
    extra = info.get(gpx.name, {})

    feature = {
        "type":"Feature",
        "properties":{
            "name": extra.get("title") or name,
            "date": date,
            "distance": f"{distance_m/1000:.2f} km",
            "ascent": f"{round(ascent):.0f} m"
        },
        "geometry":{"type":"LineString","coordinates":[[lon,lat] for lat,lon in points]}
    }
    (OUT_DIR/out_name).write_text(json.dumps(feature, ensure_ascii=False, separators=(",",":")), encoding="utf-8")

    manifest.append({
        "file": out_name,
        "gpx": gpx.name,
        "name": extra.get("title") or name,
        "date": date,
        "distance": f"{distance_m/1000:.2f} km",
        "ascent": f"{round(ascent):.0f} m",
        "blog": extra.get("blog",""),
        "komoot": extra.get("komoot","")
    })

keep={x["file"] for x in manifest}
for f in OUT_DIR.glob("*.geojson"):
    if f.name not in keep: f.unlink()

(OUT_DIR/"routes.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Built {len(manifest)} route(s).")
