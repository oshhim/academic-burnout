// EMPath+ mark, redrawn as vector from the original brand logo: an orbit with three
// nodes, an inner "C", and a centre node with a path forward to an arrow point.
// Single source for the in-app <Logo> and the generated icon PNGs
// (scripts/generate-icons.mjs). Coordinates use a 100 x 100 box.


// Orbit: open on the right, closed by a chevron into the arrow node at (86, 50).
const ORBIT = 'M86 50 L74.51 29.43 A32 32 0 1 0 74.51 70.57 Z';
// Inner "C", open to the right.
const INNER = 'M59.75 36.07 A17 17 0 1 0 59.75 63.93';
const NODES: [number, number][] = [
  [50, 18],
  [18, 50],
  [50, 82],
  [50, 50],
  [86, 50],
];

/** The mark alone. Nodes are rings (holes punched with a mask), so it works on any background. */
export function markSvg(color: string, { size = 100, scale = 1 } = {}) {
  const offset = (100 - 100 * scale) / 2;
  const nodes = NODES.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="6.5" fill="white"/>`).join('');
  const holes = NODES.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2.6" fill="black"/>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 100 100">
  <defs><mask id="m" maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="100">
    <g transform="translate(${offset - 2 * scale} ${offset}) scale(${scale})">
      <g fill="none" stroke="white" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">
        <path d="${ORBIT}"/><path d="${INNER}"/><path d="M50 50 L86 50"/>
      </g>${nodes}${holes}
    </g>
  </mask></defs>
  <rect width="100" height="100" fill="${color}" mask="url(#m)"/>
</svg>`;
}

/** Transparent mark coloured with the brand gradient (cyan -> indigo -> violet), for dark screens. */
export function gradientMarkSvg({ size = 100, scale = 1 } = {}) {
  return markSvg('url(#lg)', { size, scale }).replace(
    '<defs>',
    '<defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4CD7F6"/><stop offset="0.5" stop-color="#8083FF"/><stop offset="1" stop-color="#A855F7"/></linearGradient>',
  );
}

// ---------- App icon: "twilight aurora + glass logo" (G6) ----------

const TWILIGHT = '#272B4D';
const GLASS_DEFS =
  '<linearGradient id="gm" x1="0" y1="0" x2="0.4" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.98"/><stop offset="0.55" stop-color="#E6E7FF" stop-opacity="0.78"/><stop offset="1" stop-color="#C7C9FF" stop-opacity="0.55"/></linearGradient>';
const AURORA_DEFS =
  '<radialGradient id="a1" cx="85%" cy="5%" r="80%"><stop offset="0" stop-color="#6366F1" stop-opacity="0.7"/><stop offset="0.6" stop-color="#6366F1" stop-opacity="0.12"/><stop offset="1" stop-color="#6366F1" stop-opacity="0"/></radialGradient>' +
  '<radialGradient id="a2" cx="5%" cy="30%" r="55%"><stop offset="0" stop-color="#4CD7F6" stop-opacity="0.3"/><stop offset="1" stop-color="#4CD7F6" stop-opacity="0"/></radialGradient>';
const AURORA_RECTS = `<rect width="100" height="100" fill="${TWILIGHT}"/><rect width="100" height="100" fill="url(#a1)"/><rect width="100" height="100" fill="url(#a2)"/>`;

/** The mark as frosted glass: bright at the top, fading softly (transparent background). */
export function glassMarkSvg({ size = 100, scale = 1 } = {}) {
  return markSvg('url(#gm)', { size, scale }).replace('<defs>', `<defs>${GLASS_DEFS}`);
}

/** Twilight navy with the purple and cyan aurora glow (no mark): Android background layer. */
export function auroraSvg({ size = 100 } = {}) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 100 100"><defs>${AURORA_DEFS}</defs>${AURORA_RECTS}</svg>`;
}

/** Full app icon: twilight aurora background with the glass mark. */
export function appIconSvg({ size = 100, radius = 0, scale = 0.64 } = {}) {
  const mark = glassMarkSvg({ scale }).replace(/^<svg[^>]*>|<\/svg>\s*$/g, '');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 100 100">
  <defs>${AURORA_DEFS}<clipPath id="r"><rect width="100" height="100" rx="${radius}"/></clipPath></defs>
  <g clip-path="url(#r)">${AURORA_RECTS}</g>
  ${mark}
</svg>`;
}
