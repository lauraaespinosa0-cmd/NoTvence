// Paleta calcada de app/static/css/style.css (:root) para mantener la identidad visual de NotVence.
export const colors = {
  bg: "#050617",
  bgDeep: "#01020f",
  bgGradientTop: "#02033c",
  bgGradientMid: "#07072a",
  panel: "#1b2029",
  panelSolid: "#161b22",
  panelSoft: "#21262d",
  primary: "#238636",
  primaryHover: "#2ea043",
  accent: "#8b5cf6",
  accentSoft: "#6d5dfc",
  success: "#238636",
  warning: "#d29922",
  danger: "#da3633",
  info: "#388bfd",
  text: "#f0f6fc",
  muted: "#8b949e",
  border: "#30363d",
};

export const statusColor: Record<string, string> = {
  success: colors.success,
  warning: colors.warning,
  danger: colors.danger,
  info: colors.info,
};
