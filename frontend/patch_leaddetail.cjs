const fs = require('fs');

let code = fs.readFileSync('src/components/LeadDetailDrawer.tsx', 'utf8');

// Fix 1: Rule component style
code = code.replace(
  'function Rule() {\n  return <div style={{ width: "100%", height: 1, background: color.rule }} />;\n}',
  'function Rule() {\n  return <div style={{ width: "100%", height: 3, background: color.ink }} />;\n}'
);

// Fix 2: Drawer spacing
// "Divider gap after the Identity block (20px) is ~2.5x the gap used at every other block transition (8px) — normalize to 8px."
code = code.replace(
  '<div style={{ display: "flex", gap: 8, marginTop: 20 }}>\n        <LeadStatusBadge status={lead.status} />',
  '<div style={{ display: "flex", gap: 8, marginTop: 8 }}>\n        <LeadStatusBadge status={lead.status} />'
);

// Drawer Shell gap
// We can change gap in the content area from 16 to 8 to tighten the transitions.
code = code.replace(
  '<div style={{ flex: 1, overflowY: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>',
  '<div style={{ flex: 1, overflowY: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 8 }}>'
);

// Fix 3: Action Row order and right alignment
code = code.replace(
  '<div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: "auto", paddingTop: 8 }}>',
  '<div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: "auto", paddingTop: 8, justifyContent: "flex-end" }}>'
);

// We need to re-order the buttons: maybe put Suppress on the far left by using margin-right: auto on its container, or something similar.
// Currently the row is:
// Copy vCard
// Suppress
// Tag
// Push to CRM
// Let's modify the row to group (Suppress) ... (Copy vCard, Tag, Push to CRM)
const actionsRowHtml = `<div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: "auto", paddingTop: 8, justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <NeoButton
            variant="destructive"
            size="sm"
            loading={updateLead.isPending}
            onClick={() => updateLead.mutate({ suppressed: !lead.suppressed })}
          >
            {lead.suppressed ? "Unsuppress" : "Suppress"}
          </NeoButton>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <NeoButton variant="ghost" size="sm" onClick={() => {
            const vcard = [
              "BEGIN:VCARD",
              "VERSION:3.0",
              \`FN:\${lead.name ?? ""}\`,
              lead.phone ? \`TEL:\${lead.phone.split(",")[0].trim()}\` : "",
              lead.email ? \`EMAIL:\${lead.email.split(",")[0].trim()}\` : "",
              lead.website ? \`URL:\${lead.website}\` : "",
              "END:VCARD",
            ].filter(Boolean).join("\n");
            const blob = new Blob([vcard], { type: "text/vcard" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = \`\${lead.name ?? "lead"}.vcf\`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
          }}>
            Copy vCard
          </NeoButton>
          <NeoButton
            variant="ghost"
            size="sm"
            onClick={() => {
              const next = window.prompt("Tags (comma-separated)", lead.tags.join(", "));
              if (next === null) return;
              updateLead.mutate({ tags: next.split(",").map((t) => t.trim()).filter(Boolean) });
            }}
          >
            Tag
          </NeoButton>
          <NeoButton variant="primary" size="sm" disabled>
            Push to CRM
          </NeoButton>
        </div>
      </div>`;

// Replace the old action block (we will use regex or careful exact replace)
code = code.replace(
  /<div style=\{\{\s*display: "flex", gap: 8, flexWrap: "wrap", marginTop: "auto", paddingTop: 8\s*\}\}>[\s\S]*?<\/DrawerShell>/,
  actionsRowHtml + '\n    </DrawerShell>'
);

fs.writeFileSync('src/components/LeadDetailDrawer.tsx', code);
console.log("Patched LeadDetailDrawer.tsx");
