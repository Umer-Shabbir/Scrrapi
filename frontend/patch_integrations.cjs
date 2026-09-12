const fs = require("fs");
let content = fs.readFileSync("src/pages/Integrations.tsx", "utf-8");

// 1. Remove empty state and always render the grid
content = content.replace(
  /\{cardsQuery\.data && cardsQuery\.data\.every[\s\S]+?NO INTEGRATIONS CONNECTED[\s\S]+?<\/NeoButton>\n\s+<\/div>\n\s+\)\}/,
  ""
);

content = content.replace(
  /\{cardsQuery\.data && cardsQuery\.data\.some\(\(c\) => c\.status === "connected"\) && \(/,
  `{cardsQuery.data && (`
);

// 2. Make Webhook event text clickable
content = content.replace(
  /<span style=\{\{ fontFamily: font\.body, fontWeight: 500, fontSize: 12\.5, color: color\.ink \}\}>\n\s+\{EVENT_LABEL\[key\] \?\? key\}\n\s+<\/span>/g,
  `<span onClick={() => toggleEvent(key)} style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink, cursor: "pointer" }}>\n                {EVENT_LABEL[key] ?? key}\n              </span>`
);

// 3. Signing secret mono styling: 
// Maybe the "Not generated yet..." needs NOT to be in mono, or maybe there's a specific requirement.
// Let's use font.mono for the secret and font.body for the fallback text. Wait, or maybe just adjusting the size?
content = content.replace(
  /\{revealedSecret \?\? config\.signingSecretMasked \?\? "Not generated yet — Save to create one"\}/,
  `{revealedSecret ?? config.signingSecretMasked ? (\n                <span style={{ fontFamily: font.mono }}>{revealedSecret ?? config.signingSecretMasked}</span>\n              ) : (\n                <span style={{ fontFamily: font.body, fontStyle: "italic", color: color.ink60 }}>Not generated yet — Save to create one</span>\n              )}`
);
content = content.replace(
  /<span style=\{\{ fontFamily: font\.mono, fontSize: 12, color: color\.ink, wordBreak: "break-all" \}\}>/,
  `<span style={{ fontSize: 12, color: color.ink, wordBreak: "break-all" }}>`
);

fs.writeFileSync("src/pages/Integrations.tsx", content);
