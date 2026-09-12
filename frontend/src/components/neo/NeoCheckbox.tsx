// Form/Checkbox (page "01 — Components", node 20:6). 18px square, 3px ink
// border, checked fill blue with a white 2.5px-stroke tick -- square
// joins/caps, no rounding (cross-cutting #6: checked state was solid
// ink-black with no tick wherever this doesn't get used).

import { color } from "../../theme/neobrutalist";

interface NeoCheckboxProps {
  checked: boolean;
  onChange?: () => void;
  disabled?: boolean;
}

export default function NeoCheckbox({ checked, onChange, disabled }: NeoCheckboxProps) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      style={{
        width: 18,
        height: 18,
        padding: 0,
        display: "grid",
        placeItems: "center",
        background: disabled ? color.sand : checked ? color.blue : color.white,
        border: `3px solid ${disabled ? color.rule : color.ink}`,
        borderRadius: 0,
        cursor: disabled ? "default" : "pointer",
        flexShrink: 0,
        transition: "background 120ms cubic-bezier(0.2, 0, 0, 1), border-color 120ms cubic-bezier(0.2, 0, 0, 1)",
      }}
    >
      {checked && (
        <svg key="tick" className="neo-pop" width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path
            d="M2.5 7.5L5.5 10.5L11.5 3.5"
            stroke={color.white}
            strokeWidth="2.5"
            strokeLinecap="square"
            strokeLinejoin="miter"
          />
        </svg>
      )}
    </button>
  );
}
