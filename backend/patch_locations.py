
with open("frontend/src/pages/Locations.tsx", encoding="utf-8") as f:
    text = f.read()

# Add radius states
state_declarations_after = """  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  const [radiusCenterLat, setRadiusCenterLat] = useState<string>("");
  const [radiusCenterLon, setRadiusCenterLon] = useState<string>("");
  const [radiusKm, setRadiusKm] = useState<string>("50");
  const [radiusType, setRadiusType] = useState<"zip" | "city">("zip");
  const [radiusLoading, setRadiusLoading] = useState(false);

  const [boundsMinLat, setBoundsMinLat] = useState<string>("");
  const [boundsMaxLat, setBoundsMaxLat] = useState<string>("");
  const [boundsMinLon, setBoundsMinLon] = useState<string>("");
  const [boundsMaxLon, setBoundsMaxLon] = useState<string>("");
  const [boundsType, setBoundsType] = useState<"zip" | "city">("zip");
  const [boundsLoading, setBoundsLoading] = useState(false);

  async function performRadiusSearch() {
    if (!radiusCenterLat || !radiusCenterLon || !radiusKm) return;
    setRadiusLoading(true);
    try {
      const res = await api.get<{items: any[], total: number, truncated: boolean}>(
        `/api/geo/radius?lat=${radiusCenterLat}&lon=${radiusCenterLon}&radius_km=${radiusKm}&type=${radiusType}&limit=500`
      );
      if (res.items.length === 0) {
        setNotice("Radius search found no results.");
      } else {
        const batch = res.items.map(item => ({
          id: item.id,
          label: radiusType === "zip" ? `${item.name}, ${item.cityName}` : item.name,
          zipCode: radiusType === "zip" ? item.name : null,
          city: radiusType === "zip" ? item.cityName : item.name,
          region: null,
          country: null,
        }));
        queue(batch);
      }
    } catch (e: any) {
      setNotice(`Error: ${e.message}`);
    } finally {
      setRadiusLoading(false);
    }
  }

  async function performBoundsSearch() {
    if (!boundsMinLat || !boundsMaxLat || !boundsMinLon || !boundsMaxLon) return;
    setBoundsLoading(true);
    try {
      const res = await api.get<{items: any[], total: number, truncated: boolean}>(
        `/api/geo/bounds?min_lat=${boundsMinLat}&max_lat=${boundsMaxLat}&min_lon=${boundsMinLon}&max_lon=${boundsMaxLon}&type=${boundsType}&limit=500`
      );
      if (res.items.length === 0) {
        setNotice("Polygon/Bounds search found no results.");
      } else {
        const batch = res.items.map(item => ({
          id: item.id,
          label: boundsType === "zip" ? `${item.name}, ${item.cityName}` : item.name,
          zipCode: boundsType === "zip" ? item.name : null,
          city: boundsType === "zip" ? item.cityName : item.name,
          region: null,
          country: null,
        }));
        queue(batch);
      }
    } catch (e: any) {
      setNotice(`Error: ${e.message}`);
    } finally {
      setBoundsLoading(false);
    }
  }
"""

text = text.replace("  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());", state_declarations_after)

# Replace the disabled logic in TABS rendering
text = text.replace('const disabled = t === "Radius" || t === "Polygon";', 'const disabled = false;')

# Replace the radius placeholder:
old_radius_placeholder = """          {(tab === "Radius" || tab === "Polygon") && (
            <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
              {tab} search isn&rsquo;t available yet — no geo-shape search exists on the backend.
            </p>
          )}"""

new_radius_ui = """          {tab === "Radius" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", gap: 12 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }} onClick={() => setRadiusType("zip")}>
                  <NeoRadio checked={radiusType === "zip"} onChange={() => setRadiusType("zip")} />
                  <span style={{ fontFamily: font.body, fontSize: 13, color: color.ink }}>ZIP Codes</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }} onClick={() => setRadiusType("city")}>
                  <NeoRadio checked={radiusType === "city"} onChange={() => setRadiusType("city")} />
                  <span style={{ fontFamily: font.body, fontSize: 13, color: color.ink }}>Cities</span>
                </label>
              </div>
              <div style={{ display: "flex", gap: 12 }}>
                <input value={radiusCenterLat} onChange={e => setRadiusCenterLat(e.target.value)} placeholder="Lat (e.g. 30.2672)" style={{ flex: 1, height: 40, border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, boxSizing: "border-box" }} />
                <input value={radiusCenterLon} onChange={e => setRadiusCenterLon(e.target.value)} placeholder="Lon (e.g. -97.7431)" style={{ flex: 1, height: 40, border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, boxSizing: "border-box" }} />
                <input value={radiusKm} onChange={e => setRadiusKm(e.target.value)} placeholder="Radius (km)" style={{ width: 100, flexShrink: 0, height: 40, border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, boxSizing: "border-box" }} />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <NeoButton variant="primary" disabled={!radiusCenterLat || !radiusCenterLon || !radiusKm || radiusLoading} onClick={performRadiusSearch}>
                  {radiusLoading ? "Searching..." : "Search & Add"}
                </NeoButton>
              </div>
            </div>
          )}

          {tab === "Polygon" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", gap: 12 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }} onClick={() => setBoundsType("zip")}>
                  <NeoRadio checked={boundsType === "zip"} onChange={() => setBoundsType("zip")} />
                  <span style={{ fontFamily: font.body, fontSize: 13, color: color.ink }}>ZIP Codes</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }} onClick={() => setBoundsType("city")}>
                  <NeoRadio checked={boundsType === "city"} onChange={() => setBoundsType("city")} />
                  <span style={{ fontFamily: font.body, fontSize: 13, color: color.ink }}>Cities</span>
                </label>
              </div>
              <div style={{ display: "flex", gap: 12 }}>
                <input value={boundsMinLat} onChange={e => setBoundsMinLat(e.target.value)} placeholder="Min Lat" style={{ flex: 1, height: 40, border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, boxSizing: "border-box" }} />
                <input value={boundsMaxLat} onChange={e => setBoundsMaxLat(e.target.value)} placeholder="Max Lat" style={{ flex: 1, height: 40, border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, boxSizing: "border-box" }} />
                <input value={boundsMinLon} onChange={e => setBoundsMinLon(e.target.value)} placeholder="Min Lon" style={{ flex: 1, height: 40, border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, boxSizing: "border-box" }} />
                <input value={boundsMaxLon} onChange={e => setBoundsMaxLon(e.target.value)} placeholder="Max Lon" style={{ flex: 1, height: 40, border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, boxSizing: "border-box" }} />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <NeoButton variant="primary" disabled={!boundsMinLat || !boundsMaxLat || !boundsMinLon || !boundsMaxLon || boundsLoading} onClick={performBoundsSearch}>
                  {boundsLoading ? "Searching..." : "Search & Add"}
                </NeoButton>
              </div>
            </div>
          )}"""

target_text_found = old_radius_placeholder in text
if not target_text_found:
    print("UI placeholder not found!")
    import sys
    sys.exit(1)

text = text.replace(old_radius_placeholder, new_radius_ui)

with open("frontend/src/pages/Locations.tsx", "w", encoding="utf-8") as f:
    f.write(text)

print("Patched successfully")
