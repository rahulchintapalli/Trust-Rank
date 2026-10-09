/**
 * Score Visualization & Color Utilities for TrustRank
 */

/**
 * Returns color hex/CSS variable based on score threshold.
 * @param {number} value Score between 0.0 and 1.0
 * @param {boolean} invert True if lower score is better (e.g., contradiction)
 * @returns {string} CSS color string
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
 * Animate progress bar widths and SVG circular progress paths after DOM insert.
 * @param {HTMLElement} parentElement Container element
 */
function animateScoreVisuals(parentElement = document) {
  requestAnimationFrame(() => {
    // Fill horizontal progress bars
    const fillBars = parentElement.querySelectorAll('.score-bar-fill');
    fillBars.forEach(bar => {
      const targetVal = parseFloat(bar.dataset.value || '0');
      bar.style.width = `${Math.round(targetVal * 100)}%`;
    });

    // Fill circular composite SVGs
    const circles = parentElement.querySelectorAll('.composite-svg-fill');
    circles.forEach(circle => {
      const targetOffset = circle.dataset.targetOffset;
      circle.style.strokeDashoffset = targetOffset;
    });
  });
}
