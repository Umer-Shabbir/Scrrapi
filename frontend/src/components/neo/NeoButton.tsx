// Button/Primary, Button/Secondary, Button/Ghost from the neobrutalist system
// (page "01 — Components"). Loading swaps the label for the 3-square marching
// indicator per spec rather than a spinner.

import { color, font, shadow } from "../../theme/neobrutalist";

interface NeoButtonProps {
  children: React.ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "destructive";
  onClick?: () => void;
  type?: "button" | "submit";
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
  size?: "md" | "sm";
}

// Marches left-to-right in a loop (each square's opacity pulses out of phase)
// rather than sitting static -- a "loading" indicator that doesn't move reads
// as stalled, not busy.
function MarchingSquares({ fill }: { fill: string }) {
  return (
    <span style={{ display: "flex", gap: 4 }}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="neo-pulse-square"
          style={{ width: 6, height: 6, background: fill, display: "block", animationDelay: `${i * 160}ms` }}
        />
      ))}
    </span>
  );
}

export default function NeoButton({
  children,
  variant = "primary",
  onClick,
  type = "button",
  disabled,
  loading,
  fullWidth,
  size = "md",
}: NeoButtonProps) {
  const inactive = disabled || loading;
  const height = size === "sm" ? 32 : 48;

  const base: React.CSSProperties = {
    height,
    width: fullWidth ? "100%" : undefined,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "0 24px",
    fontFamily: font.body,
    fontWeight: 700,
    fontSize: 13,
    textTransform: "uppercase",
    cursor: inactive ? "default" : "pointer",
    boxSizing: "border-box",
    // A button's own label must never wrap -- a narrow flex row (e.g. Lead
    // Detail's 4-button actions row) would otherwise squeeze a longer label
    // like "Push to CRM" onto two lines instead of shrinking its neighbors.
    whiteSpace: "nowrap",
    flexShrink: 0,
  };

  let style: React.CSSProperties;
  let labelColor: string = color.ink;
  // Only bordered/shadowed variants get the hover-lift/press-settle treatment
  // -- ghost has no shadow to shorten, and an inactive button shouldn't
  // invite interaction it doesn't accept.
  let liftable = false;
  if (variant === "ghost") {
    style = { ...base, border: "3px solid transparent", background: "transparent" };
  } else if (inactive) {
    style = { ...base, border: `3px solid ${color.ink}`, background: color.sand };
    labelColor = color.ink60;
  } else if (variant === "primary") {
    style = { ...base, border: `3px solid ${color.ink}`, background: color.blue, boxShadow: shadow.sm };
    labelColor = color.white;
    liftable = true;
  } else if (variant === "destructive") {
    style = { ...base, border: `3px solid ${color.ink}`, background: color.pink, boxShadow: shadow.sm };
    labelColor = color.white;
    liftable = true;
  } else {
    style = { ...base, border: `3px solid ${color.ink}`, background: color.white };
    liftable = true;
  }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={inactive}
      className={liftable ? "neo-btn-liftable" : undefined}
      style={{ ...style, color: labelColor }}
    >
      {loading ? <MarchingSquares fill={labelColor} /> : children}
    </button>
  );
}
