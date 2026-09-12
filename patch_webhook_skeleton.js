const fs = require("fs");
const file = "G:/Scrrapi/frontend/src/pages/WebhookDeliveryLog.tsx";
let code = fs.readFileSync(file, "utf8");

code = code.replace(/import InlineWarning from "\.\.\/components\/neo\/InlineWarning";/, `import InlineWarning from "../components/neo/InlineWarning";\nimport { SkeletonTable, SkeletonCard } from "../components/neo/Skeleton";`);

// Remove the custom SkeletonRow
code = code.replace(/function SkeletonRow\(\) \{[\s\S]*?\}\n\n/, "");

// Replace the responsive table part
const tableRegex = /(<div className="neo-responsive-table" style=\{\{ background: color\.white, border: `3px solid \$\{color\.ink\}`, overflowX: "auto" \}\}>\s*<table[\s\S]*?<\/table>\s*<\/div>)/;

code = code.replace(tableRegex, `<div className="neo-responsive-table" style={{ overflowX: "auto" }}>
        {logQuery.isLoading ? (
          <SkeletonTable rows={4} columns={6} />
        ) : (
          <div style={{ background: color.white, border: \`3px solid \${color.ink}\` }}>
            <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 760 }}>
              <thead>
                <tr style={{ background: color.sand }}>
                  {["TIMESTAMP", "EVENT", "STATUS", "ATTEMPT", "DURATION", "ACTIONS"].map((h) => (
                    <th key={h} style={{ textAlign: "left", padding: "10px 12px", fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.315px", color: color.ink }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {log?.deliveries.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ padding: 24, textAlign: "center", fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
                      No deliveries recorded yet for this webhook.
                    </td>
                  </tr>
                )}

                {log?.deliveries.map((d, i) => {
                  const expanded = expandedId === d.id;
                  return (
                    <Fragment key={d.id}>
                      <tr
                        onClick={() => setExpandedId(expanded ? null : d.id)}
                        className="neo-row-enter"
                        style={{ borderTop: \`3px solid \${color.rule}\`, cursor: "pointer", ["--neo-delay" as string]: \`\${Math.min(i, 12) * 24}ms\` }}
                      >
                        <td style={{ padding: "10px 12px", fontFamily: font.mono, fontSize: 12, color: color.ink }}>
                          {d.createdAt.replace("T", " ").slice(0, 19)}
                        </td>
                        <td style={{ padding: "10px 12px", fontFamily: font.body, fontSize: 13, color: color.ink }}>{d.event}</td>
                        <td style={{ padding: "10px 12px" }}>
                          <StatusChip delivery={d} />
                        </td>
                        <td style={{ padding: "10px 12px", fontFamily: font.mono, fontSize: 12, color: color.ink }}>
                          {d.attempt}/{d.attemptMax}
                        </td>
                        <td style={{ padding: "10px 12px", fontFamily: font.mono, fontSize: 12, color: color.ink }}>
                          {formatDuration(d.durationMs)}
                        </td>
                        <td style={{ padding: "10px 12px" }}>
                          <button
                            type="button"
                            disabled={disabled || replayingId === d.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              replay.mutate(d.id);
                            }}
                            style={{
                              border: "none",
                              background: "transparent",
                              cursor: disabled ? "default" : "pointer",
                              padding: 0,
                              fontFamily: font.body,
                              fontWeight: 500,
                              fontSize: 12.5,
                              color: disabled ? color.ink60 : color.blue,
                            }}
                          >
                            {replayingId === d.id ? "REPLAYING…" : "REPLAY"}
                          </button>
                        </td>
                      </tr>
                      {expanded && (
                        <tr>
                          <td colSpan={6} style={{ padding: 0 }}>
                            <DeliveryDetail delivery={d} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>`);

const cardsRegex = /(<div className="neo-responsive-cards">)[\s\S]*?(<p style=\{\{ margin: 0, padding: "24px 0", textAlign: "center", fontFamily: font\.body, fontSize: 13, color: color\.ink60 \}\}>\s*No deliveries recorded yet for this webhook\.\s*<\/p>)/;

code = code.replace(cardsRegex, `$1
        {logQuery.isLoading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonCard key={i} height={84} />
            ))}
          </div>
        )}

        {log?.deliveries.length === 0 && !logQuery.isLoading && (
          $2
        )`);

fs.writeFileSync(file, code);
