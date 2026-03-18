import requests, json

base = "http://127.0.0.1:5000"

# 1. Status
r = requests.get(f"{base}/api/status")
print("STATUS:", r.json())

# 2. Upload
with open(r"C:\SurveyCAD\sample_data\sample_survey.csv", "rb") as fh:
    r2 = requests.post(f"{base}/api/upload",
                       files={"file": ("sample_survey.csv", fh, "text/csv")})
data = r2.json()
print(f"UPLOAD: success={data['success']}, rows={data['row_count']}, codes={data['unique_codes']}")

# 3. Generate SCR + DXF with polyline for C IB
body = {
    "rows":           data["rows"],
    "modes":          ["scr", "dxf"],
    "text_height":    1.0,
    "offset":         True,
    "polyline_codes": ["C IB"],
    "units":          "meters",
}
r3 = requests.post(f"{base}/api/generate", json=body)
out = r3.json()
print(f"GENERATE: success={out['success']}")
for f in out.get("files", []):
    print(f"  FILE: {f['name']}  {f['size_bytes']} bytes")
for lg in out.get("logs", []):
    print(f"  LOG: {lg}")
for e in out.get("errors", []):
    print(f"  ERR: {e}")

# 4. Test download endpoint
import os, urllib.request
scr_url = f"{base}/api/download/survey_output.scr"
r4 = requests.get(scr_url)
print(f"DOWNLOAD SCR: status={r4.status_code}, content-length={len(r4.content)} bytes")

print("\\nAll tests passed!")
