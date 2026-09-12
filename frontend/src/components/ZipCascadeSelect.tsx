// Country -> State -> City -> ZIP(s). Backed by /api/geo/* (geo reference DB,
// GeoNames-seeded worldwide). Legacy equivalent: LocationEditForm.
//
// Every level is a type-to-search `Autocomplete`, not a dropdown of options:
// seeded with the whole world the geo DB holds ~250 countries, ~4k regions,
// ~1.1M cities and ~1.8M postal codes, so only the country list is small enough
// to ship whole and filter in the browser. Region, city and ZIP search the
// server on a debounce and show the head of the list until you type.
//
// The last level is the one that matters: it is the unit a job is built from,
// so it is a multi-select with a select-all. It runs in one of two modes.
//
// **ZIP mode** (121 countries) — City is a single select carrying an extra
// "All cities" option, and the multi-select holds that area's postal codes.
//
// **Area mode** (the other 131) — those countries have no postal code system at
// all, so nothing can supply ZIPs for them and there is no point pretending
// otherwise. What the ZIP is *for* is cutting a city into pieces small enough
// that Maps' ~120-result ceiling stops binding, and the seeded place list does
// that too: Lagos State is 33 areas. So the City single-select is replaced by a
// multi-select of the region's places, and everything downstream is identical —
// a target with a city but no zipCode.
//
// The server decides which mode applies (`regionHasZips` on /api/geo/cities);
// asking it per region rather than guessing from a country list means a country
// that gains postal data in a later seed starts working with no code change.
//
// Selection is emitted upward as ready-to-queue LocationTargets rather than as
// ids; the parent page queues them, it doesn't need to know about the geo DB.

import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import CheckBoxIcon from "@mui/icons-material/CheckBox";
import CheckBoxOutlineBlankIcon from "@mui/icons-material/CheckBoxOutlineBlank";
import PublicIcon from "@mui/icons-material/Public";
import { api } from "../api/client";
import { useDebounced } from "../hooks/useDebounced";
import type { CityPage, GeoOption, LocationTarget, ZipOption, ZipPage } from "../types";

/** Pseudo-city meaning "draw ZIPs from every city in the selected region". */
const ALL_CITIES: GeoOption = { id: "__all_cities__", name: "All cities in this state" };

// Matches MIN_SEARCH_LEN in backend/app/api/routers/locations.py: below this the
// server ignores the term, so sending it is a wasted round trip.
const MIN_SEARCH_LEN = 2;

interface Props {
  /** Fires on every change with the current ZIP selection, already queue-shaped. */
  onChange: (targets: LocationTarget[]) => void;
  /** Bump to reset the ZIP selection — used after a batch is queued. */
  resetKey?: number;
}

/**
 * "78701, Austin, Texas, United States" — the string appended to the keyword in
 * the Maps query, so it has to read like something a person would type. The ZIP
 * leads because it's the part that actually narrows the search.
 */
export function zipLabel(
  zip: ZipOption,
  region: GeoOption | null,
  country: GeoOption | null,
): string {
  return [zip.name, zip.cityName, region?.name, country?.name].filter(Boolean).join(", ");
}

function toTarget(
  zip: ZipOption,
  region: GeoOption | null,
  country: GeoOption | null,
): LocationTarget {
  return {
    id: zip.id,
    label: zipLabel(zip, region, country),
    zipCode: zip.name,
    city: zip.cityName,
    region: region?.name ?? null,
    country: country?.name ?? null,
  };
}

/** Only send a search term the server will act on. */
function searchParam(term: string): string {
  const trimmed = term.trim();
  return trimmed.length >= MIN_SEARCH_LEN ? `&q=${encodeURIComponent(trimmed)}` : "";
}

export default function ZipCascadeSelect({ onChange, resetKey = 0 }: Props) {
  const [country, setCountry] = useState<GeoOption | null>(null);
  const [region, setRegion] = useState<GeoOption | null>(null);
  const [city, setCity] = useState<GeoOption | null>(null);
  const [selectedZips, setSelectedZips] = useState<ZipOption[]>([]);
  // Area mode's selection: the region's places, standing in for postal codes.
  const [selectedAreas, setSelectedAreas] = useState<GeoOption[]>([]);
  // ZIP mode, one city deep, where that particular city happens to have no
  // postal codes even though its region does. Queue the city itself.
  const [useCityInstead, setUseCityInstead] = useState(false);

  // What's in each search box, debounced before it reaches the server. These are
  // the Autocompletes' controlled `inputValue` too, so they have to track every
  // change MUI makes — including the "reset" it fires to display the option you
  // just picked. Filtering those out leaves the box showing the fragment you
  // typed ("tex") instead of the thing you chose ("Texas").
  const [regionTerm, setRegionTerm] = useState("");
  const [cityTerm, setCityTerm] = useState("");
  const [zipTerm, setZipTerm] = useState("");
  const regionQ = useDebounced(regionTerm);
  const cityQ = useDebounced(cityTerm);
  const zipQ = useDebounced(zipTerm);

  const countries = useQuery({
    queryKey: ["geo", "countries"],
    queryFn: () => api.get<GeoOption[]>("/api/geo/countries"),
  });

  const regions = useQuery({
    queryKey: ["geo", "regions", country?.id, regionQ],
    queryFn: () =>
      api.get<GeoOption[]>(`/api/geo/regions?country=${country!.id}${searchParam(regionQ)}`),
    enabled: !!country,
    // Without this the list empties on every keystroke and the dropdown flickers
    // between "no options" and results.
    placeholderData: keepPreviousData,
  });

  const cities = useQuery({
    queryKey: ["geo", "cities", region?.id, cityQ],
    queryFn: () =>
      api.get<CityPage>(`/api/geo/cities?region=${region!.id}${searchParam(cityQ)}`),
    enabled: !!region,
    placeholderData: keepPreviousData,
  });

  // Which mode this region runs in. Assume ZIPs until the server says otherwise,
  // so the layout doesn't flip while the first city query is still in flight —
  // and ignore placeholder data, which is the *previous* region's answer and
  // would otherwise flash the wrong mode on every country change.
  const areaMode =
    cities.isSuccess && !cities.isPlaceholderData && !cities.data.regionHasZips;

  // One query for both scopes: "All cities" swaps the parameter, not the shape.
  const wholeRegion = city?.id === ALL_CITIES.id;
  const zipScope = wholeRegion ? `region=${region?.id}` : `city=${city?.id}`;

  const zips = useQuery({
    queryKey: ["geo", "zips", wholeRegion ? `region:${region?.id}` : `city:${city?.id}`, zipQ],
    queryFn: () => api.get<ZipPage>(`/api/geo/zips?${zipScope}&q=${encodeURIComponent(zipQ.trim())}`),
    enabled: !areaMode && (wholeRegion ? !!region : !!city),
    placeholderData: keepPreviousData,
  });

  // In area mode the region's places *are* the options, so the same search box
  // that filters cities in ZIP mode filters the selectable areas here.
  const areas = useQuery({
    queryKey: ["geo", "areas", region?.id, zipQ],
    queryFn: () =>
      api.get<CityPage>(`/api/geo/cities?region=${region!.id}${searchParam(zipQ)}&limit=200`),
    enabled: areaMode && !!region,
    placeholderData: keepPreviousData,
  });

  const cityOptions = useMemo(
    () => [ALL_CITIES, ...(cities.data?.items ?? [])],
    [cities.data],
  );
  const zipOptions = useMemo(() => zips.data?.items ?? [], [zips.data]);
  const areaOptions = useMemo(() => areas.data?.items ?? [], [areas.data]);

  const cityTarget = useMemo<LocationTarget | null>(
    () =>
      city && !wholeRegion
        ? {
            id: city.id,
            label: [city.name, region?.name, country?.name].filter(Boolean).join(", "),
            zipCode: null,
            city: city.name,
            region: region?.name ?? null,
            country: country?.name ?? null,
          }
        : null,
    [city, wholeRegion, region, country],
  );

  /** An area (city) as a queue target: same shape as a ZIP target, minus the ZIP. */
  const areaTarget = (area: GeoOption): LocationTarget => ({
    id: area.id,
    label: [area.name, region?.name, country?.name].filter(Boolean).join(", "),
    zipCode: null,
    city: area.name,
    region: region?.name ?? null,
    country: country?.name ?? null,
  });

  // The parent only ever wants queue-shaped targets, and the label needs the
  // region/country names — which live in their own state, so this has to
  // re-emit when those change, not just when the selection does.
  useEffect(() => {
    if (areaMode) {
      onChange(selectedAreas.map(areaTarget));
      return;
    }
    const cityFallback = useCityInstead && cityTarget ? [cityTarget] : [];
    onChange([...selectedZips.map((z) => toTarget(z, region, country)), ...cityFallback]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    areaMode,
    selectedAreas,
    selectedZips,
    region?.id,
    country?.id,
    useCityInstead,
    cityTarget?.label,
  ]);

  useEffect(() => {
    if (!resetKey) return;
    setSelectedZips([]);
    setSelectedAreas([]);
    setUseCityInstead(false);
  }, [resetKey]);

  function pickCountry(value: GeoOption | null) {
    setCountry(value);
    setRegion(null);
    setCity(null);
    setSelectedZips([]);
    setSelectedAreas([]);
    setRegionTerm("");
    setCityTerm("");
    setZipTerm("");
  }

  function pickRegion(value: GeoOption | null) {
    setRegion(value);
    setCity(null);
    setSelectedZips([]);
    setSelectedAreas([]);
    setCityTerm("");
    setZipTerm("");
  }

  function pickCity(value: GeoOption | null) {
    setCity(value);
    setSelectedZips([]);
    setUseCityInstead(false);
    setZipTerm("");
  }

  /** Adds everything currently listed to the selection, keeping what's already picked. */
  function selectAllShown() {
    if (areaMode) {
      setSelectedAreas((prev) => {
        const byId = new Map(prev.map((a) => [a.id, a]));
        for (const a of areaOptions) byId.set(a.id, a);
        return [...byId.values()];
      });
      return;
    }
    setSelectedZips((prev) => {
      const byId = new Map(prev.map((z) => [z.id, z]));
      for (const z of zipOptions) byId.set(z.id, z);
      return [...byId.values()];
    });
  }

  const searching = (q: string) => q.trim().length >= MIN_SEARCH_LEN;

  // The two modes share the whole footer — same select-all, same counts, same
  // truncation warning — so they resolve to one set of values here rather than
  // duplicating that block per mode.
  const optionCount = areaMode ? areaOptions.length : zipOptions.length;
  const selectedCount = areaMode ? selectedAreas.length : selectedZips.length;
  const page = areaMode ? areas.data : zips.data;
  const unit = areaMode ? "areas" : "ZIPs";
  const scopeNoun = areaMode ? "state" : wholeRegion ? "state" : "city";

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={2} useFlexGap flexWrap="wrap">
        <Autocomplete
          size="small"
          sx={{ minWidth: 240 }}
          options={countries.data ?? []}
          value={country}
          onChange={(_, value) => pickCountry(value)}
          loading={countries.isLoading}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          getOptionLabel={(o) => o.name}
          renderInput={(params) => (
            <TextField {...params} label="Country" placeholder="Type to search" />
          )}
        />

        <Autocomplete
          size="small"
          sx={{ minWidth: 240 }}
          options={regions.data ?? []}
          value={region}
          onChange={(_, value) => pickRegion(value)}
          inputValue={regionTerm}
          onInputChange={(_, value) => setRegionTerm(value)}
          // The server already ranked and narrowed; re-filtering in the browser
          // would hide rows that matched on a substring the input no longer holds.
          filterOptions={(x) => x}
          loading={regions.isFetching}
          disabled={!country}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          getOptionLabel={(o) => o.name}
          renderInput={(params) => (
            <TextField
              {...params}
              label="State / Region"
              placeholder={country ? "Type to search" : "Pick a country first"}
            />
          )}
        />

        {/* Area mode has no city step — the region's places are the selection
            below, so a single-city drill-down would only get in the way. */}
        <Autocomplete
          size="small"
          sx={{ minWidth: 260, display: areaMode ? "none" : undefined }}
          options={cityOptions}
          value={city}
          onChange={(_, value) => pickCity(value)}
          inputValue={cityTerm}
          onInputChange={(_, value) => setCityTerm(value)}
          filterOptions={(x) => x}
          loading={cities.isFetching}
          disabled={!region}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          getOptionLabel={(o) => o.name}
          renderOption={(props, option) => {
            const { key, ...rest } = props as typeof props & { key: string };
            if (option.id === ALL_CITIES.id) {
              return (
                <li key={key} {...rest}>
                  <PublicIcon fontSize="small" sx={{ mr: 1, opacity: 0.6 }} />
                  <em>{option.name}</em>
                </li>
              );
            }
            return (
              <li key={key} {...rest}>
                {option.name}
              </li>
            );
          }}
          renderInput={(params) => (
            <TextField
              {...params}
              label="City"
              placeholder={region ? "Type to search" : "Pick a state first"}
              InputProps={{
                ...params.InputProps,
                endAdornment: (
                  <>
                    {cities.isFetching && <CircularProgress size={16} />}
                    {params.InputProps.endAdornment}
                  </>
                ),
              }}
            />
          )}
        />
      </Stack>

      {!areaMode && cities.data?.truncated && (
        <Typography variant="caption" color="text.secondary">
          Showing {cities.data.items.length} of {cities.data.total} cities — keep typing to
          narrow it.
        </Typography>
      )}

      {areaMode && (
        <Alert severity="info">
          {country?.name} has no postal code system, so there are no ZIPs to load — for
          about half the world&apos;s countries none exist to find. These places are the search
          areas instead: pick some or take all of them, and each becomes its own search.
        </Alert>
      )}

      {areaMode ? (
        <Autocomplete
          multiple
          disableCloseOnSelect
          size="small"
          options={areaOptions}
          value={selectedAreas}
          onChange={(_, value) => setSelectedAreas(value)}
          inputValue={zipTerm}
          onInputChange={(_, value) => setZipTerm(value)}
          filterOptions={(x) => x}
          loading={areas.isFetching}
          disabled={!region}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          getOptionLabel={(o) => o.name}
          limitTags={8}
          renderOption={(props, option, { selected }) => {
            const { key, ...rest } = props as typeof props & { key: string };
            return (
              <li key={key} {...rest}>
                <Checkbox
                  icon={<CheckBoxOutlineBlankIcon fontSize="small" />}
                  checkedIcon={<CheckBoxIcon fontSize="small" />}
                  style={{ marginRight: 8 }}
                  checked={selected}
                />
                {option.name}
              </li>
            );
          }}
          renderTags={(value, getTagProps) =>
            value.map((option, index) => {
              const { key, ...rest } = getTagProps({ index });
              return <Chip key={key} {...rest} size="small" label={option.name} />;
            })
          }
          renderInput={(params) => (
            <TextField
              {...params}
              label={`Areas in ${region?.name ?? "this state"}`}
              placeholder={region ? "Type to filter, or select all" : "Pick a state first"}
            />
          )}
        />
      ) : (
        <Autocomplete
          multiple
          disableCloseOnSelect
          size="small"
          options={zipOptions}
          value={selectedZips}
          onChange={(_, value) => setSelectedZips(value)}
          inputValue={zipTerm}
          onInputChange={(_, value) => setZipTerm(value)}
          filterOptions={(x) => x}
          loading={zips.isFetching}
          disabled={!city}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          getOptionLabel={(o) => o.name}
          // A state runs to thousands of postal codes; rendering every chip turns
          // the field into a wall. The count below is the useful part anyway.
          limitTags={12}
          renderOption={(props, option, { selected }) => {
            const { key, ...rest } = props as typeof props & { key: string };
            return (
              <li key={key} {...rest}>
                <Checkbox
                  icon={<CheckBoxOutlineBlankIcon fontSize="small" />}
                  checkedIcon={<CheckBoxIcon fontSize="small" />}
                  style={{ marginRight: 8 }}
                  checked={selected}
                />
                <Box component="span" sx={{ fontVariantNumeric: "tabular-nums", mr: 1 }}>
                  {option.name}
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {option.cityName}
                </Typography>
              </li>
            );
          }}
          renderTags={(value, getTagProps) =>
            value.map((option, index) => {
              const { key, ...rest } = getTagProps({ index });
              return <Chip key={key} {...rest} size="small" label={option.name} />;
            })
          }
          renderInput={(params) => (
            <TextField
              {...params}
              label="ZIP codes"
              placeholder={city ? "Type to filter, or select all" : "Pick a city first"}
            />
          )}
        />
      )}

      <Stack direction="row" spacing={1.5} alignItems="center" useFlexGap flexWrap="wrap">
        <Button
          size="small"
          variant="outlined"
          disabled={optionCount === 0}
          onClick={selectAllShown}
        >
          {searching(zipQ)
            ? `Add all ${optionCount} matching`
            : `Select all ${optionCount} ${unit}`}
        </Button>
        <Button
          size="small"
          color="inherit"
          disabled={selectedCount === 0}
          onClick={() => (areaMode ? setSelectedAreas([]) : setSelectedZips([]))}
        >
          Clear selection
        </Button>
        <Typography variant="body2" color="text.secondary">
          {selectedCount} selected · {optionCount} shown
          {page && ` · ${page.total} in this ${scopeNoun}`}
        </Typography>
      </Stack>

      {page?.truncated && (
        <Alert severity="warning">
          Showing the first {optionCount} of {page.total} {unit} — the buttons above only
          take what&apos;s listed. Type to narrow it{areaMode ? "" : ", or pick a single city"},
          to reach the rest.
        </Alert>
      )}
      {!areaMode && zips.isSuccess && zipOptions.length === 0 && city && searching(zipQ) && (
        <Alert severity="info">No postal codes here match that.</Alert>
      )}

      {/* ZIP mode, but this one city has none even though its region does. The
          cascade already knows exactly which city/state/country was picked, so
          offer it rather than making the user retype it into the free-text box. */}
      {!areaMode && zips.isSuccess && zips.data.total === 0 && cityTarget && !searching(zipQ) && (
        <Alert
          severity="info"
          action={
            <Button
              size="small"
              variant={useCityInstead ? "contained" : "outlined"}
              onClick={() => setUseCityInstead((on) => !on)}
            >
              {useCityInstead ? "Selected" : `Use ${cityTarget.city}`}
            </Button>
          }
        >
          No postal codes for this city. Queue the city as a single search instead.
        </Alert>
      )}
      {zips.isError && <Alert severity="error">{(zips.error as Error).message}</Alert>}
      {areas.isError && <Alert severity="error">{(areas.error as Error).message}</Alert>}
    </Stack>
  );
}
