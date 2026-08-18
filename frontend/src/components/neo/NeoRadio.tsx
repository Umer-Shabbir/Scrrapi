// Form/Radio (page "01 — Components", node 20:11). Same 18px square as
// Checkbox with a 3px ink border -- "this system has no circles" is spec
// verbatim (cross-cutting #5: radios render as circles wherever this doesn't
// get used). Checked state is an inset 8px ink square, not a dot.

import { color } from "../../theme/neobrutalist";

interface NeoRadioProps {
  checked: boolean;
  onChange?: () => void;
  disabled?: boolean;
}

export default function NeoRadio({ checked, onChange, disabled }: NeoRadioProps) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      style={{
        width: 18,
        height: 18,
        padding: 0,
        display: "grid",
        placeItems: "center",
        background: disabled ? color.sand : color.white,
        border: `3px solid ${disabled ? color.rule : color.ink}`,
        cursor: disabled ? "default" : "pointer",
        flexShrink: 0,
        transition: "border-color 120ms cubic-bezier(0.2, 0, 0, 1)",
      }}
    >
      {checked && (
        <span key="dot" className="neo-pop" style={{ width: 8, height: 8, background: disabled ? color.ink60 : color.ink }} />
      )}
    </button>
  );
}
