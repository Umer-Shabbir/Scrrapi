const fs = require("fs");
let content = fs.readFileSync("src/pages/Suppression.tsx", "utf-8");

content = content.replace(
  `        <div style={{ background: color.pink, color: color.white, padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>`,
  `        <div style={{ background: color.pink, color: color.white, borderBottom: \`3px solid \${color.ink}\`, padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>`
);

content = content.replace(
  `        <div style={{ background: color.ink, color: color.white, padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>`,
  `        <div style={{ background: color.ink, borderBottom: \`3px solid \${color.ink}\`, color: color.white, padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>`
);

fs.writeFileSync("src/pages/Suppression.tsx", content);
