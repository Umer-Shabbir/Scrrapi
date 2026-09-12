// Locations screen (Figma [SCREEN] locations). Builds the ZIP queue a job runs
// over. Legacy equivalent: UploadLocationsForm / LocationEditForm.
//
// The search is per postal code: search down Country -> State -> City, then take
// some or all of that area's ZIPs, and each one becomes its own Maps search.
// Two ways in, same as before: the geo cascade (ZipCascadeSelect, reused as-is
// -- still plain MUI Autocomplete, since a full restyle of that component is
// out of scope for this screen) and straight typing.
//
// Figma also shows Radius/Polygon tabs and "Saved Area Sets" -- neither has a
// backend (no GeoJSON/radius geo search, no set registry). Radius/Polygon are
// disabled tabs, same treatment as the New Job Wizard's step 2. Saved Area
// Sets is implemented for real via localStorage, same pattern as Categories'
// saved packs -- not a stub.
//
// The queue is the shared job draft (state/JobDraftContext); there is no
// locations table server-side.

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import ZipCascadeSelect from "../components/ZipCascadeSelect";
import { api, ApiError } from "../api/client";
import NeoButton from "../components/neo/NeoButton";
import NeoRadio from "../components/neo/NeoRadio";
import InlineWarning from "../components/neo/InlineWarning";
import {
  LOCATION_SEPARATORS,
  labelToLocation,
  useJobDraft,
  type QueueMode,
} from "../state/JobDraftContext";
import { color, font } from "../theme/neobrutalist";
import type { GeoOption, LocationTarget } from "../types";

const AREA_SETS_STORAGE_KEY = "area_sets";
const TABS = ["Cascade", "Radius", "Polygon", "Type an area"] as const;
type Tab = (typeof TABS)[number];

interface AreaSet {
  name: string;
  locations: LocationTarget[];
}

function loadAreaSets(): AreaSet[] {
  try {
    const raw = localStorage.getItem(AREA_SETS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveAreaSets(sets: AreaSet[]): void {
  localStorage.setItem(AREA_SETS_STORAGE_KEY, JSON.stringify(sets));
}

function Card({ title, meta, action, children }: { title: string; meta?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: color.white,
        border: `3px solid ${color.ink}`,
        boxShadow: "6px 6px 0px 0px #111",
        padding: 24,
        display: "flex",
        flexDirection: "column",
        gap: 20,
        boxSizing: "border-box",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink, whiteSpace: "nowrap" }}>{title}</h2>
        {meta && <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: "12.5px", color: color.ink60 }}>{meta}</span>}
        <div style={{ flex: 1 }} />
        {action}
      </div>
      {children}
    </div>
  );
}

function MapPreview({ count }: { count: number }) {
  const markers = useMemo(
    () => Array.from({ length: Math.min(count, 24) }, () => ({ x: Math.random() * 90 + 5, y: Math.random() * 80 + 10 })),
    // Regenerating on every render would jitter the markers on unrelated re-renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [Math.min(count, 24)],
  );
  return (
    <div style={{ background: color.sand, border: `3px solid ${color.ink}`, height: 200, position: "relative", overflow: "hidden" }}>
      {count === 0 ? (
        <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center" }}>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>No areas queued yet</p>
        </div>
      ) : (
        markers.map((m, i) => (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${m.x}%`,
              top: `${m.y}%`,
              width: 10,
              height: 10,
              background: color.yellow,
              border: `3px solid ${color.ink}`,
              transform: "rotate(45deg)",
            }}
          />
        ))
      )}
    </div>
  );
}

export default function Locations() {
  const navigate = useNavigate();
  const { locations, keywords, addLocations, removeLocation, clearLocations } = useJobDraft();

  const [tab, setTab] = useState<Tab>("Cascade");
  const [selected, setSelected] = useState<LocationTarget[]>([]);
  const [mode, setMode] = useState<QueueMode>("append");
  const [typed, setTyped] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [areaSets, setAreaSets] = useState<AreaSet[]>(loadAreaSets);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

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


  const countries = useQuery({
    queryKey: ["geo", "countries"],
    queryFn: () => api.get<GeoOption[]>("/api/geo/countries"),
  });
  const unseeded = countries.isSuccess && countries.data.length === 0;

  function queue(batch: LocationTarget[]) {
    if (batch.length === 0) return;
    const previous = locations.length;
    const added = addLocations(batch, mode);
    setNotice(
      mode === "replace"
        ? `Queue replaced — ${added} area(s) queued, ${previous} removed.`
        : `Added ${added} of ${batch.length} — ${batch.length - added} already queued.`,
    );
  }

  function commitTyped() {
    const batch = typed
      .split(LOCATION_SEPARATORS)
      .map((part) => part.trim())
      .filter(Boolean)
      .map(labelToLocation);
    if (batch.length === 0) return;
    queue(batch);
    setTyped("");
  }

  function saveCurrentAsSet() {
    const name = window.prompt("Name this area set:");
    if (!name?.trim()) return;
    const next = [...areaSets.filter((s) => s.name !== name.trim()), { name: name.trim(), locations }];
    setAreaSets(next);
    saveAreaSets(next);
  }

  function applyAreaSet(set: AreaSet) {
    const added = addLocations(set.locations, "append");
    setNotice(`Added ${added} of ${set.locations.length} area(s) from "${set.name}".`);
  }

  function deleteAreaSet(name: string) {
    const next = areaSets.filter((s) => s.name !== name);
    setAreaSets(next);
    saveAreaSets(next);
  }

  function toggleGroup(key: string) {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // Group the queue by region (fallback: the location's own label) for the
  // collapsible-group presentation the Figma queue panel uses.
  const groups = useMemo(() => {
    const byRegion = new Map<string, LocationTarget[]>();
    for (const loc of locations) {
      const key = loc.region ?? loc.label;
      if (!byRegion.has(key)) byRegion.set(key, []);
      byRegion.get(key)!.push(loc);
    }
    return [...byRegion.entries()];
  }, [locations]);

  return (
    <div>
      <div className="neo-responsive-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>LOCATIONS</h1>
          <p style={{ margin: "6px 0 0", fontFamily: font.body, fontSize: 13, color: color.ink60, maxWidth: 700 }}>
            Build the area queue this job runs over — cascade by ZIP, or type an area by hand.{" "}
            {keywords.length} keyword(s) × {locations.length} area(s) = {keywords.length * locations.length} target(s).
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.315px", color: color.ink60 }}>
            WHEN ADDING
          </span>
          {(["append", "replace"] as const).map((m) => (
            <label key={m} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }} onClick={() => setMode(m)}>
              <NeoRadio checked={mode === m} onChange={() => setMode(m)} />
              <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, color: mode === m ? color.ink : color.ink60 }}>
                {m.toUpperCase()}
              </span>
            </label>
          ))}
        </div>
      </div>

      {unseeded && (
        <div style={{ background: color.sand, border: `2px solid ${color.rule}`, padding: 12, marginBottom: 20, fontFamily: font.body, fontSize: 12, color: color.ink }}>
          The geo reference database is empty — run <code>npm run seed</code> to import GeoNames,
          or type locations by hand below (those search a whole area at once rather than ZIP by ZIP).
        </div>
      )}
      {countries.isError && (
        <div style={{ background: color.white, border: `3px solid ${color.ink}`, borderLeft: `6px solid ${color.pink}`, padding: 12, marginBottom: 20 }}>
          <InlineWarning tone="ink" fontSize={12} fontWeight={400}>
            {countries.error instanceof ApiError ? countries.error.message : "Couldn't reach the API server"}
          </InlineWarning>
        </div>
      )}

      <div className="neo-responsive-row" style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
        <Card title="ADD AREAS">
          <div style={{ display: "flex", gap: 24, borderBottom: `2px solid ${color.rule}` }}>
            {TABS.map((t) => {
              const disabled = false;
              return (
                <button
                  key={t}
                  type="button"
                  disabled={disabled}
                  onClick={() => setTab(t)}
                  style={{
                    border: "none",
                    background: "transparent",
                    padding: "0 0 8px",
                    cursor: disabled ? "default" : "pointer",
                    borderBottom: tab === t ? `3px solid ${color.ink}` : "3px solid transparent",
                    marginBottom: -2,
                  }}
                >
                  <span
                    style={{
                      fontFamily: font.body,
                      fontWeight: 700,
                      fontSize: "12.5px",
                      letterSpacing: "0.375px",
                      textTransform: "uppercase",
                      color: disabled ? color.rule : tab === t ? color.ink : color.ink60,
                    }}
                  >
                    {t}
                  </span>
                </button>
              );
            })}
          </div>

          {tab === "Radius" && (
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
          )}

          {tab === "Cascade" && (
            <>
              <ZipCascadeSelect onChange={setSelected} resetKey={resetKey} />
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <NeoButton
                  variant="primary"
                  disabled={selected.length === 0}
                  onClick={() => {
                    queue(selected);
                    setSelected([]);
                    setResetKey((k) => k + 1);
                  }}
                >
                  {mode === "replace" ? `Replace with ${selected.length} area(s)` : `Add ${selected.length} area(s)`}
                </NeoButton>
                <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
                  {mode === "replace" ? `Discards the ${locations.length} already queued.` : "Keeps what's already queued; duplicates are skipped."}
                </p>
              </div>
            </>
          )}

          {tab === "Type an area" && (
            <>
              <div>
                <p style={{ margin: "0 0 6px", fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.3675px", textTransform: "uppercase", color: color.ink }}>
                  Type an area
                </p>
                <input
                  value={typed}
                  placeholder="Austin, TX"
                  onChange={(e) => setTyped(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key !== "Enter") return;
                    e.preventDefault();
                    commitTyped();
                  }}
                  style={{ width: "100%", height: 40, boxSizing: "border-box", border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, fontSize: 13 }}
                />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <NeoButton variant="primary" disabled={!typed.trim()} onClick={commitTyped}>
                  Add
                </NeoButton>
                <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
                  Searched as one query for the whole area, so it returns far less than the same
                  area covered ZIP by ZIP.
                </p>
              </div>
            </>
          )}

          {notice && <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>{notice}</p>}
        </Card>

        <div className="neo-responsive-fill" style={{ width: 380, flexShrink: 0, display: "flex", flexDirection: "column", gap: 20 }}>
          <Card title="MAP PREVIEW">
            <MapPreview count={locations.length} />
          </Card>

          <Card title="AREA SETS">
            {areaSets.length === 0 ? (
              <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
                No saved sets yet — queue some areas, then save them below.
              </p>
            ) : (
              areaSets.map((set) => (
                <div key={set.name} style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 0", borderBottom: `2px solid ${color.rule}` }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: "12.5px", color: color.ink }}>{set.name}</p>
                    <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 10, color: color.ink60 }}>
                      {set.locations.length} AREA{set.locations.length === 1 ? "" : "S"}
                    </p>
                  </div>
                  <NeoButton variant="secondary" size="sm" onClick={() => applyAreaSet(set)}>
                    Use
                  </NeoButton>
                  <button
                    type="button"
                    onClick={() => deleteAreaSet(set.name)}
                    style={{ border: "none", background: "transparent", cursor: "pointer", color: color.ink60, fontSize: 14, padding: 4 }}
                  >
                    ✕
                  </button>
                </div>
              ))
            )}
            <NeoButton variant="ghost" size="sm" onClick={saveCurrentAsSet} disabled={locations.length === 0}>
              + Save current queue as set
            </NeoButton>
          </Card>
        </div>
      </div>

      <div style={{ marginTop: 20 }}>
        <Card
          title="QUEUE"
          meta={`${locations.length} AREAS`}
          action={
            <>
              <NeoButton variant="secondary" size="sm" disabled={locations.length === 0} onClick={clearLocations}>
                Clear all
              </NeoButton>
              <NeoButton
                variant="primary"
                size="sm"
                disabled={locations.length === 0}
                onClick={() => navigate(keywords.length === 0 ? "/categories" : "/")}
              >
                {keywords.length === 0 ? "Add keywords next" : "Back to job"}
              </NeoButton>
            </>
          }
        >
          {locations.length === 0 ? (
            <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
              Nothing queued yet. Search down to a city above and take some or all of its ZIP
              codes — or its areas, where postal codes don&rsquo;t exist.
            </p>
          ) : (
            groups.map(([groupKey, groupLocations]) => {
              const collapsed = collapsedGroups.has(groupKey);
              const zipCount = groupLocations.filter((l) => l.zipCode).length;
              return (
                <div key={groupKey} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <button
                      type="button"
                      onClick={() => toggleGroup(groupKey)}
                      style={{ display: "flex", alignItems: "center", gap: 8, border: "none", background: "transparent", cursor: "pointer", padding: 0 }}
                    >
                      <span style={{ fontSize: 10, color: color.ink }}>{collapsed ? "▶" : "▼"}</span>
                      <span style={{ fontFamily: font.head, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>
                        {groupKey.toUpperCase()} · {zipCount || groupLocations.length} {zipCount ? "ZIP CODES" : "AREA(S)"}
                      </span>
                    </button>
                    <NeoButton variant="ghost" size="sm" onClick={() => groupLocations.forEach((l) => removeLocation(l.id))}>
                      Clear group
                    </NeoButton>
                  </div>
                  {!collapsed && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                      {groupLocations.map((l) => (
                        <span
                          key={l.id}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            border: `2px solid ${color.ink}`,
                            padding: "3px 8px",
                            fontFamily: font.body,
                            fontSize: "12.5px",
                            color: color.ink,
                          }}
                        >
                          {l.zipCode ?? l.label}
                          <button
                            type="button"
                            onClick={() => removeLocation(l.id)}
                            style={{ border: "none", background: "transparent", padding: 0, cursor: "pointer", fontSize: 10, color: color.ink }}
                          >
                            ✕
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </Card>
      </div>
    </div>
  );
}
