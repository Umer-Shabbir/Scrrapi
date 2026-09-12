// Categories screen (Figma [SCREEN] categories). Free-text keyword entry + CSV
// upload + saved packs. Legacy equivalent: UploadCategoriesForm.
//
// The keyword list is the shared job draft (state/JobDraftContext), not local
// state -- the Dashboard/Wizard pair it with the location draft to build
// JobTargets. The backend only supplies autocomplete suggestions
// (GET /api/categories) and parses an uploaded file (POST /api/categories/upload)
// -- categories are never persisted server-side.
//
// Figma's "Category Packs" (built-in HOME SERVICES/LEGAL packs) and "Synonym
// Suggestions" (accept/reject keyword expansion) have no backend at all -- no
// pack registry, no synonym service. Built-in packs are omitted rather than
// faked; "save current list as a pack" is a real feature backed by
// localStorage (same persistence model JobDraftContext already uses), not a
// stub. Synonym Suggestions is omitted entirely -- there's no synonym data
// anywhere, client or server, to expand from.

import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import NeoButton from "../components/neo/NeoButton";
import InlineWarning from "../components/neo/InlineWarning";
import { KEYWORD_SEPARATORS, useJobDraft } from "../state/JobDraftContext";
import { color, font } from "../theme/neobrutalist";
import type { CategoryUpload } from "../types";

const PACKS_STORAGE_KEY = "keyword_packs";

interface KeywordPack {
  name: string;
  keywords: string[];
}

function loadPacks(): KeywordPack[] {
  try {
    const raw = localStorage.getItem(PACKS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function savePacks(packs: KeywordPack[]): void {
  localStorage.setItem(PACKS_STORAGE_KEY, JSON.stringify(packs));
}

function Card({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: color.white,
        border: `3px solid ${color.ink}`,
        boxShadow: "6px 6px 0px 0px #111",
        padding: 24,
        display: "flex",
        flexDirection: "column",
        gap: 16,
        width: "100%",
        boxSizing: "border-box",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink, whiteSpace: "nowrap" }}>{title}</h2>
        <div style={{ flex: 1 }} />
        {action}
      </div>
      {children}
    </div>
  );
}

export default function Categories() {
  const navigate = useNavigate();
  const { keywords, addKeywords, removeKeyword, clearKeywords, locations } = useJobDraft();

  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [packs, setPacks] = useState<KeywordPack[]>(loadPacks);
  const fileInput = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const suggestions = useQuery({
    queryKey: ["categories", "suggestions"],
    queryFn: () => api.get<string[]>("/api/categories/"),
    staleTime: Infinity,
  });

  const upload = useMutation({
    mutationFn: (file: File) => api.upload<CategoryUpload>("/api/categories/upload", file),
    onSuccess: (data) => {
      const added = addKeywords(data.keywords);
      setError(null);
      const parts = [`Added ${added} of ${data.count} keyword(s)`];
      if (data.skipped) parts.push(`${data.skipped} skipped in file`);
      if (data.truncated) parts.push("file truncated at the row limit");
      setNotice(`${parts.join(" — ")}.`);
    },
    onError: (err: Error) => {
      setNotice(null);
      setError(err.message);
    },
  });

  function addDraft() {
    const parsed = draft.split(KEYWORD_SEPARATORS);
    if (parsed.every((p) => !p.trim())) return;
    addKeywords(parsed);
    setDraft("");
  }

  function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) upload.mutate(file);
    event.target.value = "";
  }

  function saveCurrentAsPack() {
    const name = window.prompt("Name this pack:");
    if (!name?.trim()) return;
    const next = [...packs.filter((p) => p.name !== name.trim()), { name: name.trim(), keywords: [...keywords] }];
    setPacks(next);
    savePacks(next);
  }

  function applyPack(pack: KeywordPack) {
    const added = addKeywords(pack.keywords);
    setNotice(`Added ${added} of ${pack.keywords.length} keyword(s) from "${pack.name}".`);
  }

  function deletePack(name: string) {
    const next = packs.filter((p) => p.name !== name);
    setPacks(next);
    savePacks(next);
  }

  const uniqueCount = new Set(keywords.map((k) => k.toLowerCase())).size;

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>CATEGORIES</h1>
        <p style={{ margin: "6px 0 0", fontFamily: font.body, fontSize: 13, color: color.ink60, maxWidth: 720 }}>
          Build the keyword list a job runs over. Nothing here is saved unless you save it as a
          pack — the working list lives in your browser.
        </p>
      </div>

      <div className="neo-responsive-row" style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 20 }}>
          <Card
            title="ADD KEYWORDS"
            action={
              <>
                <NeoButton variant="secondary" size="sm" onClick={() => fileInput.current?.click()} disabled={upload.isPending}>
                  {upload.isPending ? "Uploading…" : "Upload CSV"}
                </NeoButton>
                <input ref={fileInput} type="file" accept=".csv,.txt,.tsv" hidden onChange={handleFile} />
              </>
            }
          >
            <div>
              <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.3675px", textTransform: "uppercase", color: color.ink }}>
                Keywords
              </p>
              <div style={{ marginTop: 6, border: `3px solid ${color.ink}`, minHeight: 40, display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", padding: "8px 12px", background: color.white, boxSizing: "border-box" }}>
                {keywords.map((k) => (
                  <span
                    key={k}
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
                    {k.toUpperCase()}
                    <button
                      type="button"
                      onClick={() => removeKeyword(k)}
                      style={{ border: "none", background: "transparent", padding: 0, cursor: "pointer", fontSize: 10, color: color.ink }}
                    >
                      ✕
                    </button>
                  </span>
                ))}
                <input
                  ref={inputRef}
                  value={draft}
                  placeholder={keywords.length === 0 ? "plumber, roofer, hvac repair" : ""}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key !== "Enter") return;
                    e.preventDefault();
                    addDraft();
                  }}
                  style={{ border: "none", outline: "none", fontFamily: font.body, fontSize: 13, flex: 1, minWidth: 140 }}
                />
              </div>
              <p style={{ margin: "6px 0 0", fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.4px", textTransform: "uppercase", color: color.ink60 }}>
                Comma, semicolon or newline separated
              </p>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.35px", color: color.ink60 }}>
                {keywords.length} KEYWORD{keywords.length === 1 ? "" : "S"} · {uniqueCount} UNIQUE
              </p>
              <div style={{ flex: 1 }} />
              {keywords.length > 0 && (
                <NeoButton variant="ghost" size="sm" onClick={clearKeywords}>
                  Clear all
                </NeoButton>
              )}
              <NeoButton
                variant="primary"
                size="sm"
                onClick={() => navigate(locations.length === 0 ? "/locations" : "/")}
                disabled={keywords.length === 0}
              >
                Next: locations →
              </NeoButton>
            </div>

            {error && (
              <InlineWarning tone="pink" fontSize={12} fontWeight={700}>{error}</InlineWarning>
            )}
            {notice && (
              <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>{notice}</p>
            )}

            {suggestions.isError && (
              <div style={{ background: color.sand, border: `2px solid ${color.rule}`, padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                <InlineWarning tone="ink" fontSize={12} fontWeight={700}>Suggestions unavailable</InlineWarning>
                <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
                  {suggestions.error instanceof ApiError
                    ? suggestions.error.message
                    : "Couldn't reach the API server"}
                  {" "}— you can still type keywords manually.
                </p>
                <div>
                  <NeoButton variant="ghost" size="sm" onClick={() => suggestions.refetch()}>
                    Retry
                  </NeoButton>
                </div>
              </div>
            )}
            {suggestions.data && suggestions.data.length > 0 && (
              <div>
                <p style={{ margin: "0 0 6px", fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.35px", textTransform: "uppercase", color: color.ink60 }}>
                  Suggestions
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {suggestions.data.slice(0, 12).map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => addKeywords([s])}
                      style={{
                        border: `2px solid ${color.ink}`,
                        background: color.white,
                        padding: "3px 8px",
                        fontFamily: font.body,
                        fontSize: "12.5px",
                        color: color.ink,
                        cursor: "pointer",
                      }}
                    >
                      + {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </div>

        <div className="neo-responsive-fill" style={{ width: 360, flexShrink: 0 }}>
          <Card title="CATEGORY PACKS" action={undefined}>
            {packs.length === 0 ? (
              <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
                No saved packs yet — build a keyword list, then save it below.
              </p>
            ) : (
              <div>
                {packs.map((pack) => (
                  <div
                    key={pack.name}
                    style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 0", borderBottom: `2px solid ${color.rule}` }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: "12.5px", color: color.ink }}>{pack.name}</p>
                      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.3px", color: color.ink60 }}>
                        {pack.keywords.length} KEYWORD{pack.keywords.length === 1 ? "" : "S"} · SAVED BY YOU
                      </p>
                    </div>
                    <NeoButton variant="secondary" size="sm" onClick={() => applyPack(pack)}>
                      Use pack
                    </NeoButton>
                    <button
                      type="button"
                      onClick={() => deletePack(pack.name)}
                      title="Delete pack"
                      style={{ border: "none", background: "transparent", cursor: "pointer", color: color.ink60, fontSize: 14, padding: 4 }}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
            <NeoButton variant="ghost" size="sm" onClick={saveCurrentAsPack} disabled={keywords.length === 0}>
              + Save current list as pack
            </NeoButton>
          </Card>
        </div>
      </div>
    </div>
  );
}
