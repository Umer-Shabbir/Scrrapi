// Results grid (Figma "Data/Table", results screen). Neobrutalist rebuild --
// replaces the legacy MUI DataGrid (this file's prior implementation) with the
// same plain-table + ink-border pattern already used by Results' own Targets
// tab and Schedule & Monitoring's Run History table, so the page no longer
// mixes design systems.
//
// Columns: Category, Name, Address, City/State/Country/ZIP, Phone, Email,
// Website, and the social profiles the deep crawler fills in. Country/social
// columns start hidden via a column picker (SCREENLIST's spec) -- eight extra
// columns on every run would push Website off-screen for the majority of jobs,
// which are scraped with the crawler off.
//
// Real pagination, not a client-side slice: `page`/`pageSize`/`total`/`onPage`
// drive a server-backed page-through (see pages/Results.tsx), so all of a
// job's rows are reachable rather than only the first 200.

import { useEffect, useRef, useState } from "react";
import NeoButton from "./neo/NeoButton";
import NeoCheckbox from "./neo/NeoCheckbox";
import { SkeletonTable } from "./neo/Skeleton";
import { color, font } from "../theme/neobrutalist";
import type { Result } from "../types";

interface Column {
  field: keyof Result;
  header: string;
  width: number;
  render?: (result: Result) => React.ReactNode;
}

interface Props {
  results: Result[];
  loading?: boolean;
  /** Opens the Lead Detail drawer for the clicked row. Cell-level links stop
   * propagation, so this only fires for a click on open row space. */
  onRowClick?: (result: Result) => void;

  // Server-backed pagination (all optional so a caller can still render a
  // bare unpaged slice, e.g. tests).
  page?: number;
  pageSize?: number;
  total?: number;
  onPageChange?: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
}

/** Renders an empty cell as a dash so a blank column reads as "no data", not
 * "broken" -- same convention as every other table in this app. */
function cellText(value: string | number | null | undefined): React.ReactNode {
  if (value === null || value === undefined || value === "") {
    return <span style={{ color: color.ink60 }}>—</span>;
  }
  return <>{value}</>;
}

function cellLink(value: string | null, href: (v: string) => string): React.ReactNode {
  if (!value) return cellText(value);
  return (
    <a
      href={href(value)}
      target="_blank"
      rel="noreferrer noopener"
      onClick={(e) => e.stopPropagation()}
      style={{
        color: color.blue,
        fontFamily: font.body,
        fontSize: 12,
        textDecoration: "none",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
        display: "block",
        maxWidth: "100%",
      }}
    >
      {value}
    </a>
  );
}

/** Split a multi-value contact cell ("a, b") back into its parts. */
function splitValues(value: string): string[] {
  return value.split(",").map((part) => part.trim()).filter(Boolean);
}

/** One link for the first value in a joined cell, the rest behind a "+n"
 * marker -- the first value is the one that gets dialled or mailed in
 * practice, and the row height stays fixed regardless of how many there are. */
function cellValues(value: string | null, href: (v: string) => string): React.ReactNode {
  if (!value) return cellText(value);
  const values = splitValues(value);
  const [first, ...rest] = values;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
      <a
        href={href(first)}
        target="_blank"
        rel="noreferrer noopener"
        onClick={(e) => e.stopPropagation()}
        style={{ color: color.blue, fontFamily: font.body, fontSize: 12, textDecoration: "none", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
      >
        {first}
      </a>
      {rest.length > 0 && (
        <span title={rest.join(", ")} style={{ fontFamily: font.body, fontSize: 11, color: color.ink60, flexShrink: 0 }}>
          +{rest.length}
        </span>
      )}
    </div>
  );
}

/** Social columns are one URL each; show the handle/path, link the URL. */
function cellProfile(value: string | null): React.ReactNode {
  if (!value) return cellText(value);
  let label = value;
  try {
    const url = new URL(value);
    label = `${url.pathname.replace(/^\/+|\/+$/g, "")}${url.search}` || url.host;
  } catch {
    // Not a parseable URL -- show it as stored.
  }
  return cellLink(label, () => value);
}

const BASE_COLUMNS: Column[] = [
  { field: "name", header: "Name", width: 200 },
  { field: "category", header: "Category", width: 140 },
  { field: "address", header: "Address", width: 220 },
  { field: "city", header: "City", width: 110 },
  { field: "state", header: "State", width: 90 },
  { field: "zipCode", header: "ZIP", width: 80 },
  {
    field: "phone",
    header: "Phone",
    width: 160,
    render: (r) => cellValues(r.phone, (v) => `tel:${v.replace(/[^\d+]/g, "")}`),
  },
  {
    field: "email",
    header: "Email",
    width: 220,
    render: (r) => cellValues(r.email, (v) => `mailto:${v}`),
  },
  {
    field: "website",
    header: "Website",
    width: 220,
    render: (r) => cellLink(r.website, (v) => (/^https?:\/\//i.test(v) ? v : `https://${v}`)),
  },
];

// Extra columns a normal (crawler-off) run never populates. Hidden by
// default and revealed once real data shows up in any of them (see the
// `revealed` effect below) or via the column picker.
const OPTIONAL_COLUMNS: Column[] = [
  { field: "decisionMaker", header: "Decision Maker", width: 180 },
  {
    field: "mobilePhone",
    header: "Mobile Phone",
    width: 160,
    render: (r) => cellValues(r.mobilePhone, (v) => `tel:${v.replace(/[^\d+]/g, "")}`),
  },
  { field: "reviewsCount", header: "Reviews", width: 90 },
  {
    field: "sentimentLabel",
    header: "Sentiment",
    width: 120,
    render: (r) => {
      if (!r.sentimentLabel) return cellText(r.sentimentLabel);
      const bg =
        r.sentimentLabel === "Positive"
          ? color.green
          : r.sentimentLabel === "Negative"
          ? color.pink
          : r.sentimentLabel === "Mixed"
          ? color.yellow
          : color.sand;
      return (
        <span
          style={{
            display: "inline-block",
            padding: "2px 6px",
            background: bg,
            border: `1px solid ${color.ink}`,
            fontSize: 10,
            fontWeight: 700,
            textTransform: "uppercase",
          }}
        >
          {r.sentimentLabel}
        </span>
      );
    },
  },
  { field: "painPoints", header: "Pain Points", width: 220 },
  { field: "country", header: "Country", width: 110 },
  { field: "facebook", header: "Facebook", width: 150, render: (r) => cellProfile(r.facebook) },
  { field: "instagram", header: "Instagram", width: 150, render: (r) => cellProfile(r.instagram) },
  { field: "linkedin", header: "LinkedIn", width: 150, render: (r) => cellProfile(r.linkedin) },
  { field: "twitter", header: "X / Twitter", width: 140, render: (r) => cellProfile(r.twitter) },
  { field: "youtube", header: "YouTube", width: 140, render: (r) => cellProfile(r.youtube) },
  { field: "tiktok", header: "TikTok", width: 140, render: (r) => cellProfile(r.tiktok) },
  { field: "whatsapp", header: "WhatsApp", width: 150, render: (r) => cellProfile(r.whatsapp) },
  { field: "otherSocials", header: "Other socials", width: 180 },
  { field: "latitude", header: "Latitude", width: 100 },
  { field: "longitude", header: "Longitude", width: 100 },
  {
    field: "scrapedAt",
    header: "Scraped",
    width: 160,
    render: (r) => (r.scrapedAt ? new Date(r.scrapedAt).toLocaleString() : "—"),
  },
];

const ALL_COLUMNS = [...BASE_COLUMNS, ...OPTIONAL_COLUMNS];
const PAGE_SIZE_OPTIONS = [50, 100, 250, 500];

function ColumnPicker({
  visible,
  onToggle,
}: {
  visible: Set<string>;
  onToggle: (field: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <NeoButton variant="ghost" size="sm" onClick={() => setOpen((v) => !v)}>
        Columns
      </NeoButton>
      {open && (
        <>
          <div onClick={() => setOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 10 }} />
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 4px)",
              right: 0,
              zIndex: 11,
              background: color.white,
              border: `3px solid ${color.ink}`,
              boxShadow: "6px 6px 0px 0px #111",
              padding: 12,
              width: 200,
              maxHeight: 320,
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            {OPTIONAL_COLUMNS.map((col) => (
              <label
                key={col.field}
                style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: font.body, fontSize: 12, color: color.ink, cursor: "pointer" }}
              >
                <NeoCheckbox
                  checked={visible.has(col.field)}
                  onChange={() => onToggle(col.field)}
                />
                {col.header}
              </label>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function ResultsGrid({
  results,
  loading,
  onRowClick,
  page = 1,
  pageSize = 50,
  total,
  onPageChange,
  onPageSizeChange,
}: Props) {
  const [visible, setVisible] = useState<Set<string>>(new Set());
  // Only the first reveal is automatic; after that the column picker is the
  // user's, and a later page of rows must not undo what they hid.
  const revealed = useRef(false);

  useEffect(() => {
    if (revealed.current || results.length === 0) return;
    const present = OPTIONAL_COLUMNS.filter((col) => results.some((row) => row[col.field]));
    if (present.length === 0) return;
    revealed.current = true;
    setVisible((current) => new Set([...current, ...present.map((c) => c.field)]));
  }, [results]);

  const columns = ALL_COLUMNS.filter((col) => BASE_COLUMNS.includes(col) || visible.has(col.field));

  const totalCount = total ?? results.length;
  const pageCount = Math.max(1, Math.ceil(totalCount / pageSize));
  const rangeStart = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(totalCount, page * pageSize);

  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: "6px 6px 0px 0px #111" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 16px", borderBottom: `2px solid ${color.rule}` }}>
        <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink60 }}>
          {totalCount === 0 ? "0 leads" : `Showing ${rangeStart}–${rangeEnd} of ${totalCount.toLocaleString()} leads`}
        </p>
        <ColumnPicker
          visible={visible}
          onToggle={(field) =>
            setVisible((current) => {
              const next = new Set(current);
              if (next.has(field)) next.delete(field);
              else next.add(field);
              return next;
            })
          }
        />
      </div>

      {loading && results.length === 0 ? (
        <SkeletonTable rows={10} columns={columns.length} />
      ) : (
      <>
        <div className="neo-responsive-table" style={{ overflowX: "auto", maxHeight: 560, overflowY: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 900 }}>
            <thead style={{ position: "sticky", top: 0, zIndex: 1 }}>
              <tr style={{ background: color.sand }}>
                {columns.map((col) => (
                  <th
                    key={col.field}
                    style={{
                      textAlign: "left",
                      padding: "10px 12px",
                      fontFamily: font.body,
                      fontWeight: 700,
                      fontSize: "10.5px",
                      letterSpacing: "0.35px",
                      textTransform: "uppercase",
                      color: color.ink,
                      minWidth: col.width,
                      whiteSpace: "nowrap",
                      ...(col.field === "name" ? {
                        position: "sticky",
                        left: 0,
                        background: color.sand,
                        borderRight: `2px solid ${color.ink}`,
                        zIndex: 2,
                      } : {})
                    }}
                  >
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {!loading && results.length === 0 && (
                <tr>
                  <td colSpan={columns.length} style={{ padding: "32px 16px", textAlign: "center", fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
                    No leads yet.
                  </td>
                </tr>
              )}

              {!loading &&
                results.map((result, i) => (
                  <tr
                    key={result.id}
                    className="neo-row-enter"
                    onClick={onRowClick ? () => onRowClick(result) : undefined}
                    style={{
                      borderTop: `1px solid ${color.rule}`,
                      cursor: onRowClick ? "pointer" : undefined,
                      ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms`,
                    }}
                  >
                    {columns.map((col) => (
                      <td
                        key={col.field}
                        style={{
                          padding: "10px 12px",
                          fontFamily: col.field === "zipCode" || col.field === "latitude" || col.field === "longitude" ? font.mono : font.body,
                          fontSize: 12.5,
                          color: color.ink,
                          maxWidth: col.width,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          ...(col.field === "name" ? {
                            position: "sticky",
                            left: 0,
                            backgroundColor: color.white,
                            borderRight: `2px solid ${color.ink}`,
                            zIndex: 1,
                          } : {})
                        }}
                      >
                        {col.render ? col.render(result) : cellText(result[col.field] as string | number | null)}
                      </td>
                    ))}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        <div className="neo-responsive-cards" style={{ padding: 12 }}>
          {!loading && results.length === 0 && (
            <p style={{ margin: 0, padding: "24px 0", textAlign: "center", fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
              No leads yet.
            </p>
          )}
          {!loading &&
            results.map((result, i) => (
              <div
                key={result.id}
                className="neo-row-enter"
                onClick={onRowClick ? () => onRowClick(result) : undefined}
                style={{
                  border: `3px solid ${color.ink}`,
                  background: color.white,
                  padding: 12,
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                  cursor: onRowClick ? "pointer" : undefined,
                  ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms`,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                  <div>
                    <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 14, color: color.ink }}>
                      {result.name || "—"}
                    </span>
                    {result.category && (
                      <p style={{ margin: "2px 0 0", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
                        {result.category}
                      </p>
                    )}
                  </div>
                  {result.city && (
                    <span
                      style={{
                        padding: "2px 6px",
                        border: `2px solid ${color.ink}`,
                        background: color.sand,
                        fontFamily: font.body,
                        fontWeight: 700,
                        fontSize: 10,
                        color: color.ink,
                      }}
                    >
                      {result.city}
                      {result.state ? `, ${result.state}` : ""}
                    </span>
                  )}
                </div>

                {result.address && (
                  <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink }}>
                    {result.address}
                  </p>
                )}

                <div style={{ display: "flex", flexWrap: "wrap", gap: 12, borderTop: `1px solid ${color.rule}`, paddingTop: 8 }}>
                  {result.phone && (
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 11, color: color.ink60 }}>TEL:</span>
                      {cellValues(result.phone, (v) => `tel:${v.replace(/[^\d+]/g, "")}`)}
                    </div>
                  )}
                  {result.email && (
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 11, color: color.ink60 }}>EMAIL:</span>
                      {cellValues(result.email, (v) => `mailto:${v}`)}
                    </div>
                  )}
                  {result.website && (
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 11, color: color.ink60 }}>WEB:</span>
                      {cellLink(result.website, (v) => (/^https?:\/\//i.test(v) ? v : `https://${v}`))}
                    </div>
                  )}
                </div>
              </div>
            ))}
        </div>
      </>
      )}
      {(onPageChange || onPageSizeChange) && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 16px", borderTop: `2px solid ${color.rule}`, flexWrap: "wrap", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontFamily: font.body, fontSize: 11, color: color.ink60, textTransform: "uppercase" }}>Rows per page</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange?.(Number(e.target.value))}
              style={{ border: `2px solid ${color.ink}`, background: color.white, fontFamily: font.body, fontSize: 12, color: color.ink, padding: "4px 8px", cursor: "pointer" }}
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>{size}</option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <NeoButton variant="ghost" size="sm" disabled={page <= 1} onClick={() => onPageChange?.(page - 1)}>
              ← Prev
            </NeoButton>
            <span style={{ fontFamily: font.body, fontSize: 12, color: color.ink }}>
              Page {page} of {pageCount}
            </span>
            <NeoButton variant="ghost" size="sm" disabled={page >= pageCount} onClick={() => onPageChange?.(page + 1)}>
              Next →
            </NeoButton>
          </div>
        </div>
      )}
    </div>
  );
}
