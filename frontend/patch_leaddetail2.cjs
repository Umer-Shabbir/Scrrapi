const fs = require('fs');

let code = fs.readFileSync('src/components/LeadDetailDrawer.tsx', 'utf8');

const actionsRowHtml = `      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: "auto", paddingTop: 8, justifyContent: "space-between", alignItems: "center" }}>
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

// Regex matched everything up to `</DrawerShell>`
code = code.replace(
  /<div style=\{\{\s*display: "flex", gap: 8, flexWrap: "wrap", marginTop: "auto", paddingTop: 8, justifyContent: "flex-end"\s*\}\}>[\s\S]*?<\/DrawerShell>/,
  actionsRowHtml + '\n    </DrawerShell>'
);

fs.writeFileSync('src/components/LeadDetailDrawer.tsx', code);
console.log("Patched LeadDetailDrawer.tsx again");
