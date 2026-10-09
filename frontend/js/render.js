/**
 * DOM Rendering Module for TrustRank
 * Builds result cards, score bars, circular gauges, skeletons, and error alerts.
 */

/**
 * Calculates relative time string ("2 days ago", "today", etc.)
 */
function formatRelativeTime(dateStr) {
  if (!dateStr) return 'recent';
  try {
    const cleaned = dateStr.replace('Z', '');
    const date = new Date(cleaned);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    
    if (diffDays <= 0) return 'today';
    if (diffDays === 1) return 'yesterday';
    if (diffDays < 30) return `${diffDays} days ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
    return `${Math.floor(diffDays / 365)} years ago`;
  } catch (e) {
    return dateStr;
  }
}

/**
 * Escapes HTML characters to prevent XSS.
 */
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

/**
 * Renders SVG composite progress circle.
 */
function renderCompositeCircle(score) {
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const targetOffset = circumference * (1 - score);
  const pct = Math.round(score * 100);
  const color = getScoreColor(score);

  return `
    <div class="composite-circle-box">
      <svg width="52" height="52" viewBox="0 0 52 52">
        <circle cx="26" cy="26" r="${radius}" fill="none" stroke="var(--border-color)" stroke-width="4.5"/>
        <circle class="composite-svg-fill" cx="26" cy="26" r="${radius}" fill="none" stroke-width="4.5"
          stroke="${color}" stroke-linecap="round"
          stroke-dasharray="${circumference}" stroke-dashoffset="${circumference}"
          data-target-offset="${targetOffset}"
          style="transition: stroke-dashoffset 800ms cubic-bezier(0.4, 0, 0.2, 1);"/>
      </svg>
      <span class="composite-val-text">${pct}</span>
    </div>
  `;
}

/**
 * Renders individual score bar row.
 */
function renderScoreBar(label, value, key, invert = false) {
  const color = getScoreColor(value, invert);
  const pct = Math.round(value * 100);

  return `
    <div class="score-row">
      <div class="score-meta">
        <span>${label}</span>
        <span style="color: ${color}">${pct}%</span>
      </div>
      <div class="score-bar-track">
        <div class="score-bar-fill" data-value="${value}" style="background-color: ${color};"></div>
      </div>
    </div>
  `;
}

/**
 * Renders single result card HTML string.
 */
function renderResultCard(result, index) {
  const scores = result.scores || {};
  const relevance = scores.relevance ?? 0;
  const reliability = scores.reliability ?? 0;
  const freshness = scores.freshness ?? 0;
  const contradiction = scores.contradiction ?? 0;
  const evidence = scores.evidence ?? 0;
  const composite = scores.composite ?? result.trust_rank_score ?? 0;

  const sourceType = (result.source_type || result.sourceType || 'web').toLowerCase();
  const sourceName = result.source || result.sourceName || 'Unknown';
  const pubDate = result.published_date || result.publishedDate || result.timestamp || '';
  const relativeTime = formatRelativeTime(pubDate);

  const hasAlert = result.contradiction_alert || result.contradictionAlert || false;
  const alertDetails = result.contradiction_details || result.contradictionDetails || 'Claim conflicts with top medical or empirical consensus.';
  const explanation = result.explanation || 'Evaluated across 5 TrustRank dimensions.';

  return `
    <article class="result-card" data-index="${index}">
      <div class="card-header">
        <div>
          <span class="source-badge ${sourceType}">${sourceType}</span>
          <strong style="font-size: 0.85rem; color: var(--text-primary); margin-left: 0.35rem;">${escapeHtml(sourceName)}</strong>
          <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: 0.25rem;">• ${relativeTime}</span>
        </div>

        ${hasAlert ? `
          <span class="contradiction-badge" title="${escapeHtml(alertDetails)}">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 9v4M12 17h.01"/>
              <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            </svg>
            Contradiction
          </span>
        ` : ''}
      </div>

      <p class="card-title-text" id="card-text-${index}">${escapeHtml(result.text)}</p>
      <button class="read-more-btn" data-action="toggle-text" data-index="${index}">Read more</button>

      <div class="scores-container">
        ${renderScoreBar('Relevance', relevance)}
        ${renderScoreBar('Reliability', reliability)}
        ${renderScoreBar('Freshness', freshness)}
        ${renderScoreBar('Contradiction', contradiction, 'contradiction', true)}
        ${renderScoreBar('Evidence', evidence)}
      </div>

      <div class="card-footer">
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          ${renderCompositeCircle(composite)}
          <div>
            <div style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted);">Composite</div>
            <div style="font-size: 0.8rem; color: var(--text-secondary);">5-Dimension Fusion</div>
          </div>
        </div>

        <button class="why-btn" data-action="toggle-why" data-index="${index}">
          Why this result?
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="m6 9 6 6 6-6"/>
          </svg>
        </button>
      </div>

      <div class="why-panel" id="why-panel-${index}">
        <strong style="color: var(--text-primary); display: block; margin-bottom: 0.25rem;">Score Explanation:</strong>
        <p style="color: var(--text-secondary); margin-bottom: 0.5rem;">${escapeHtml(explanation)}</p>
        ${hasAlert ? `
          <strong style="color: var(--danger-red); display: block; margin-bottom: 0.25rem;">Contradiction Flag Details:</strong>
          <p style="color: var(--danger-red);">${escapeHtml(alertDetails)}</p>
        ` : ''}
      </div>
    </article>
  `;
}

/**
 * Renders skeleton card placeholdres while fetching.
 */
function renderSkeletons(count = 3) {
  return Array(count).fill(0).map(() => `
    <div class="skeleton-card">
      <div class="skeleton-line" style="width: 40%; height: 16px; margin-bottom: 1rem;"></div>
      <div class="skeleton-line" style="width: 100%; height: 14px; margin-bottom: 0.5rem;"></div>
      <div class="skeleton-line" style="width: 90%; height: 14px; margin-bottom: 0.5rem;"></div>
      <div class="skeleton-line" style="width: 70%; height: 14px; margin-bottom: 1.5rem;"></div>
      <div class="skeleton-line" style="width: 100%; height: 60px;"></div>
    </div>
  `).join('');
}

/**
 * Renders empty state placeholder.
 */
function renderEmptyState(query = '') {
  return `
    <div style="text-align: center; padding: 4rem 1rem; color: var(--text-secondary);">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5" style="margin-bottom: 1rem;">
        <circle cx="11" cy="11" r="8"/>
        <path d="m21 21-4.34-4.34"/>
      </svg>
      <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.5rem;">
        ${query ? `No matching verified results for "${escapeHtml(query)}"` : 'No search performed yet'}
      </h3>
      <p style="font-size: 0.95rem; max-width: 450px; margin: 0 auto;">
        Ask a question above to evaluate semantic relevance, source credibility, temporal freshness, and NLI contradictions.
      </p>
    </div>
  `;
}

/**
 * Renders error alert box.
 */
function renderErrorState(message) {
  return `
    <div style="background-color: var(--danger-red-light); border: 1px solid var(--danger-red); border-radius: var(--radius); padding: 1.25rem; color: var(--danger-red); margin-bottom: 2rem;">
      <div style="font-weight: 700; margin-bottom: 0.25rem;">⚠️ Search Error</div>
      <div>${escapeHtml(message)}</div>
    </div>
  `;
}
