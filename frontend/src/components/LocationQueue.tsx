// The queued search areas: one chip per area, one job target per chip per
// keyword. Usually every chip is a ZIP, but not always — GeoNames has no postal
// codes for about 155 countries, so a city there is queued whole. Shown on both
// the Locations page (where the queue is built) and the job form (where it's
// crossed with the keywords), so it lives here rather than in either.

import { Box, Button, Chip, Stack, Typography } from "@mui/material";
import type { LocationTarget } from "../types";

interface Props {
  locations: LocationTarget[];
  onRemove: (id: string) => void;
  onClear: () => void;
  emptyHint: string;
  /** Rendered next to the header — typically a link to the page that builds this list. */
  action?: React.ReactNode;
  /** Chips beyond this are collapsed into a "+N more" count. */
  maxChips?: number;
}

/** "78701 · Austin" — the ZIP is the search, the city is how you recognise it. */
function chipLabel(location: LocationTarget): string {
  if (!location.zipCode) return location.label;
  return location.city ? `${location.zipCode} · ${location.city}` : location.zipCode;
}

export default function LocationQueue({
  locations,
  onRemove,
  onClear,
  emptyHint,
  action,
  maxChips = 60,
}: Props) {
  const shown = locations.slice(0, maxChips);
  const hidden = locations.length - shown.length;
  // A queue built by "select all" is mostly one state; worth saying which.
  const areas = [...new Set(locations.map((l) => l.region ?? l.label).filter(Boolean))];
  const zipCount = locations.filter((l) => l.zipCode).length;
  // Only claim "ZIP codes" when they all are — a mixed queue would be misreported,
  // and a city-wide entry behaves very differently from a postal-code one.
  const heading = zipCount === locations.length ? "Queued ZIP codes" : "Queued search areas";

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
        <Typography variant="subtitle2">
          {heading} ({locations.length})
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        {action}
        {locations.length > 0 && (
          <Button size="small" color="inherit" onClick={onClear}>
            Clear
          </Button>
        )}
      </Stack>

      {locations.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          {emptyHint}
        </Typography>
      ) : (
        <>
          {areas.length > 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {areas.slice(0, 4).join(", ")}
              {areas.length > 4 && ` +${areas.length - 4} more`}
              {zipCount < locations.length &&
                ` · ${zipCount} ZIP code(s), ${locations.length - zipCount} whole area(s)`}
            </Typography>
          )}
          <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
            {shown.map((location) => (
              <Chip
                key={location.id}
                label={chipLabel(location)}
                title={location.label}
                size="small"
                onDelete={() => onRemove(location.id)}
              />
            ))}
            {hidden > 0 && (
              <Chip
                label={`+${hidden} more`}
                size="small"
                variant="outlined"
                color="primary"
              />
            )}
          </Stack>
        </>
      )}
    </Box>
  );
}
