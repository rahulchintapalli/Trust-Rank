/**
 * Score Visualization & Color Utilities for TrustRank
 * Includes 5-axis Radar Polygon SVG generator.
 */

function getScoreColor(value, invert = false) {
  if (invert) {
    if (value < 0.25) return 'var(--success-green)';
    if (value < 0.50) return 'var(--warning-amber)';
    return 'var(--danger-red)';
  }
  if (value >= 0.75) return 'var(--success-green)';
  if (value >= 0.50) return 'var(--warning-amber)';
  return 'var(--danger-red)';
}

/**
 * Generates an SVG 5-axis Spider/Radar polygon chart.
 * @param {Object} scores 5-dimension scores object
 * @returns {string} SVG HTML string
 */
function renderRadarChartSVG(scores) {
  const size = 160;
  const center = size / 2;
  const radius = 60;
  
  const values = [
    scores.relevance ?? 0,
    scores.reliability ?? 0,
    scores.freshness ?? 0,
    scores.contradiction ?? 0,
    scores.evidence ?? 0
  ];

  const numAxes = 5;
  const angleStep = (2 * Math.PI) / numAxes;

  // Background polygon guide rings (100% and 50%)
  const makePolyPoints = (r) => {
    return Array.from({ length: numAxes }, (_, i) => {
      const angle = i * angleStep - Math.PI / 2;
      const x = center + r * Math.cos(angle);
      const y = center + r * Math.sin(angle);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  };

  // Data polygon points
  const dataPoints = values.map((val, i) => {
    const r = Math.max(0.05, Math.min(1.0, val)) * radius;
    const angle = i * angleStep - Math.PI / 2;
    const x = center + r * Math.cos(angle);
    const y = center + r * Math.sin(angle);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const ring100 = makePolyPoints(radius);
  const ring50 = makePolyPoints(radius * 0.5);

  return `
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="overflow: visible;">
      <!-- Guide Rings -->
      <polygon points="${ring100}" fill="none" stroke="var(--border-color)" stroke-width="1.5"/>
      <polygon points="${ring50}" fill="none" stroke="var(--border-color)" stroke-width="1" stroke-dasharray="3,3"/>
      
      <!-- Axis Lines -->
      ${Array.from({ length: numAxes }, (_, i) => {
        const angle = i * angleStep - Math.PI / 2;
        const x = center + radius * Math.cos(angle);
        const y = center + radius * Math.sin(angle);
        return `<line x1="${center}" y1="${center}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="var(--border-color)" stroke-width="1"/>`;
      }).join('')}

      <!-- Data Polygon -->
      <polygon points="${dataPoints}" fill="color-mix(in srgb, var(--primary-blue) 25%, transparent)" stroke="var(--primary-blue)" stroke-width="2.5" stroke-linejoin="round"/>
    </svg>
  `;
}

function animateScoreVisuals(parentElement = document) {
  requestAnimationFrame(() => {
    const fillBars = parentElement.querySelectorAll('.score-bar-fill');
    fillBars.forEach(bar => {
      const targetVal = parseFloat(bar.dataset.value || '0');
      bar.style.width = `${Math.round(targetVal * 100)}%`;
    });

    const circles = parentElement.querySelectorAll('.composite-svg-fill');
    circles.forEach(circle => {
      const targetOffset = circle.dataset.targetOffset;
      circle.style.strokeDashoffset = targetOffset;
    });
  });
}
