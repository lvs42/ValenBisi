####
#  import json
#from valenbisi.ingest import parse

#with open("notebooks/snapshot_0.json", encoding="utf-8") as f:
#    rows = parse(json.load(f))

#print(len(rows))   # debería ser 272 (o las que tuviera ese día)
#print(rows[0])

import json
estaciones = json.load(open("notebooks/snapshot_0.json", encoding="utf-8"))["network"]["stations"]
lats = [s["latitude"] for s in estaciones if s["latitude"] is not None]
lons = [s["longitude"] for s in estaciones if s["longitude"] is not None]
print(min(lats), max(lats), min(lons), max(lons))