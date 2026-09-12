let fs = require('fs');
let code = fs.readFileSync('src/pages/Integrations.tsx', 'utf-8');

code = code.replace(
  /<span style=\{\{\s*fontFamily:\s*font\.body,\s*fontWeight:\s*500,\s*fontSize:\s*12\.5,\s*color:\s*color\.ink\s*\}\}>\s*\{EVENT_LABEL\[key\] \?\? key\}\s*<\/span>/,
  '<span onClick={() => toggleEvent(key)} style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink, cursor: "pointer" }}>\n                {EVENT_LABEL[key] ?? key}\n              </span>'
);

fs.writeFileSync('src/pages/Integrations.tsx', code);
