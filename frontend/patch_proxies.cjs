const fs = require("fs");
let content = fs.readFileSync("src/pages/Proxies.tsx", "utf-8");

content = content.replace(
  /<StatTile label="Healthy" value=\{String\(stats.healthy\)\} fill=\{[^\}]+\} \/>/,
  `<StatTile label="Healthy" value={String(stats.healthy)} fill={color.green} />`
);
content = content.replace(
  /<StatTile label="Cooling" value=\{String\(stats.cooling\)\} fill=\{[^\}]+\} \/>/,
  `<StatTile label="Cooling" value={String(stats.cooling)} fill={color.yellow} />`
);
content = content.replace(
  /<StatTile label="Retired" value=\{String\(stats.retired\)\} \/>/,
  `<StatTile label="Retired" value={String(stats.retired)} fill={color.sand} />`
);
content = content.replace(
  /<StatTile label="Avg latency" value=\{stats.avgLatencyMs != null \? \`\$\{stats.avgLatencyMs\}ms\` : "—"\} \/>/,
  `<StatTile label="Avg latency" value={stats.avgLatencyMs != null ? \`\$\{stats.avgLatencyMs\}ms\` : "—"} fill={color.purple} />`
);
content = content.replace(
  /<StatTile\n\s+label="Block rate"\n\s+value=\{stats.blockRatePct != null \? \`\$\{stats.blockRatePct\}%\` : "—"\}\n\s+fill=\{[^\}]+\}\n\s+\/>/,
  `<StatTile\n            label="Block rate"\n            value={stats.blockRatePct != null ? \`\$\{stats.blockRatePct\}%\` : "—"}\n            fill={color.pink}\n          />`
);

fs.writeFileSync("src/pages/Proxies.tsx", content);
