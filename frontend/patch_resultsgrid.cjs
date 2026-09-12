const fs = require('fs');
let code = fs.readFileSync('src/components/ResultsGrid.tsx', 'utf-8');

// Replace table loading block with SkeletonTable fallback
const tableRegex = /<div style={{ overflowX: "auto", maxHeight: 560, overflowY: "auto" }}>[\s\S]*?(?={\(onPageChange)/;
const replacement = `{loading && results.length === 0 ? (
        <SkeletonTable rows={10} columns={columns.length} />
      ) : (
      <div style={{ overflowX: "auto", maxHeight: 560, overflowY: "auto" }}>
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
                      borderRight: \`2px solid \${color.ink}\`,
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
                    borderTop: \`1px solid \${color.rule}\`,
                    cursor: onRowClick ? "pointer" : undefined,
                    ["--neo-delay" as string]: \`\${Math.min(i, 12) * 24}ms\`,
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
                          borderRight: \`2px solid \${color.ink}\`,
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
      )}
      `;

code = code.replace(tableRegex, replacement);
fs.writeFileSync('src/components/ResultsGrid.tsx', code);
