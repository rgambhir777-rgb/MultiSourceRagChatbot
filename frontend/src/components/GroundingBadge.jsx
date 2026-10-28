import styles from "./GroundingBadge.module.css";

const VARIANTS = {
  verified: { label: "Verified against sources", icon: "✓", className: styles.ok },
  unverified: { label: "Some claims couldn't be verified", icon: "!", className: styles.warn },
  unknown: { label: "Not verified", icon: "?", className: styles.neutral },
};

/**
 * Shows whether the grounding check confirmed the answer against its sources.
 * Direct replies (greetings, chit-chat) have nothing to verify, so they get no badge.
 */
export default function GroundingBadge({ grounded, route }) {
  if (route === "direct") return null;
  const variant =
    grounded === true
      ? VARIANTS.verified
      : grounded === false
        ? VARIANTS.unverified
        : VARIANTS.unknown;
  return (
    <span className={`${styles.badge} ${variant.className}`}>
      <span aria-hidden="true" className={styles.icon}>
        {variant.icon}
      </span>
      {variant.label}
    </span>
  );
}
