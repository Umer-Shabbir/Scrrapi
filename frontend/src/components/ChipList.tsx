// A labelled bag of strings with a quick-add field. Used for the keyword and
// location drafts, which are plain string lists on both the setup pages and the
// job form.

import { useState } from "react";
import { Box, Button, Chip, Stack, TextField, Typography } from "@mui/material";

interface Props {
  label: string;
  values: string[];
  placeholder: string;
  /** Splits pasted text; keywords split on commas, locations don't. */
  separators: RegExp;
  emptyHint: string;
  onAdd: (values: string[]) => void;
  onRemove: (value: string) => void;
  onClear: () => void;
  /** Rendered next to the header — typically a link to the page that builds this list. */
  action?: React.ReactNode;
}

export default function ChipList({
  label,
  values,
  placeholder,
  separators,
  emptyHint,
  onAdd,
  onRemove,
  onClear,
  action,
}: Props) {
  const [draft, setDraft] = useState("");

  function commit() {
    const parsed = draft.split(separators);
    if (parsed.every((p) => !p.trim())) return;
    onAdd(parsed);
    setDraft("");
  }

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
        <Typography variant="subtitle2">
          {label} ({values.length})
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        {action}
        {values.length > 0 && (
          <Button size="small" color="inherit" onClick={onClear}>
            Clear
          </Button>
        )}
      </Stack>

      <Stack direction="row" spacing={1} sx={{ mb: 1.5 }}>
        <TextField
          fullWidth
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            e.preventDefault();
            commit();
          }}
        />
        <Button variant="outlined" onClick={commit} disabled={!draft.trim()}>
          Add
        </Button>
      </Stack>

      {values.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          {emptyHint}
        </Typography>
      ) : (
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
          {values.map((value) => (
            <Chip key={value} label={value} size="small" onDelete={() => onRemove(value)} />
          ))}
        </Stack>
      )}
    </Box>
  );
}
