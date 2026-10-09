/**
 * Main Application Logic for TrustRank Frontend
 * Event handlers, state management, dark mode toggle, and API orchestration.
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const themeToggleBtn = document.getElementById('theme-toggle-btn');
  const searchForm = document.getElementById('search-form');
  const queryInput = document.getElementById('query-input');
  const searchBtn = document.getElementById('search-btn');
  const optionsToggleBtn = document.getElementById('options-toggle-btn');
  const optionsContent = document.getElementById('options-content');
  const resultsGrid = document.getElementById('results-grid');
  const resultsMetaBar = document.getElementById('results-meta-bar');

  // Dimension Slider Elements
  const topKInput = document.getElementById('top-k');
  const topKVal = document.getElementById('top-k-val');
  const wRelInput = document.getElementById('w-rel');
  const wRelVal = document.getElementById('w-rel-val');
  const wSupInput = document.getElementById('w-sup');
  const wSupVal = document.getElementById('w-sup-val');
  const wFreshInput = document.getElementById('w-fresh');
  const wFreshVal = document.getElementById('w-fresh-val');
  const wConInput = document.getElementById('w-con');
  const wConVal = document.getElementById('w-con-val');
  const wEviInput = document.getElementById('w-evi');
  const wEviVal = document.getElementById('w-evi-val');

  /* ============================================
     1. DARK MODE PERSISTENCE
     ============================================ */
  const savedTheme = localStorage.getItem('trustrank-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

  if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
    document.documentElement.setAttribute('data-theme', 'dark');
    themeToggleBtn.innerHTML = '☀️';
  } else {
    document.documentElement.setAttribute('data-theme', 'light');
    themeToggleBtn.innerHTML = '🌙';
  }

  themeToggleBtn.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('trustrank-theme', newTheme);
    themeToggleBtn.innerHTML = newTheme === 'dark' ? '☀️' : '🌙';
  });

  /* ============================================
     2. COLLAPSIBLE OPTIONS & SLIDER LABELS
     ============================================ */
  optionsToggleBtn.addEventListener('click', () => {
    optionsContent.classList.toggle('open');
  });

  const setupSlider = (input, labelEl, isInteger = false) => {
    input.addEventListener('input', () => {
      labelEl.textContent = isInteger ? input.value : parseFloat(input.value).toFixed(2);
    });
  };

  setupSlider(topKInput, topKVal, true);
  setupSlider(wRelInput, wRelVal);
  setupSlider(wSupInput, wSupVal);
  setupSlider(wFreshInput, wFreshVal);
  setupSlider(wConInput, wConVal);
  setupSlider(wEviInput, wEviVal);

  function getSliderWeights() {
    return {
      wRel: parseFloat(wRelInput.value),
      wSup: parseFloat(wSupInput.value),
      wFresh: parseFloat(wFreshInput.value),
      wCon: parseFloat(wConInput.value),
      wEvi: parseFloat(wEviInput.value)
    };
  }

  /* ============================================
     3. SEARCH FORM SUBMISSION
     ============================================ */
  searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;

    const topK = parseInt(topKInput.value, 10);
    const weights = getSliderWeights();

    // Set Loading UI State
    searchBtn.disabled = true;
    searchBtn.innerHTML = `<div class="spinner"></div> Searching...`;
    resultsGrid.innerHTML = renderSkeletons(topK > 6 ? 6 : topK);
    resultsMetaBar.style.display = 'none';

    try {
      // Call API Endpoint (FastAPI)
      const data = await searchAPI(query, topK, weights);
      const results = data.results || [];
      const totalCandidates = data.total_candidates ?? results.length;
      const queryTimeMs = data.query_time_ms ?? 10;

      if (!results || results.length === 0) {
        resultsGrid.innerHTML = renderEmptyState(query);
      } else {
        // Render Results
        resultsGrid.innerHTML = results.map((res, i) => renderResultCard(res, i)).join('');
        
        // Show Meta Bar
        resultsMetaBar.style.display = 'flex';
        const flaggedCount = results.filter(r => r.contradiction_alert || r.contradictionAlert).length;
        resultsMetaBar.innerHTML = `
          <div>Found <strong>${results.length}</strong> verified results (evaluated ${totalCandidates} candidates in ${queryTimeMs}ms)</div>
          <div>${flaggedCount > 0 ? `<span style="color: var(--danger-red); font-weight: 700;">⚠️ ${flaggedCount} contradiction alert(s)</span>` : '✅ All top sources consistent'}</div>
        `;

        // Animate Visual Progress Bars & Circles
        animateScoreVisuals(resultsGrid);
      }

    } catch (err) {
      console.error('[TrustRank App Error]:', err);
      resultsGrid.innerHTML = renderErrorState(err.message || 'Failed to connect to TrustRank backend server.');
    } finally {
      searchBtn.disabled = false;
      searchBtn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/>
          <path d="m21 21-4.34-4.34"/>
        </svg>
        Search
      `;
    }
  });

  /* ============================================
     4. EVENT DELEGATION FOR CARD INTERACTION
     ============================================ */
  resultsGrid.addEventListener('click', (e) => {
    const target = e.target.closest('[data-action]');
    if (!target) return;

    const action = target.dataset.action;
    const index = target.dataset.index;

    if (action === 'toggle-text') {
      const textEl = document.getElementById(`card-text-${index}`);
      const isExpanded = textEl.classList.toggle('expanded');
      target.textContent = isExpanded ? 'Show less' : 'Read more';
    } else if (action === 'toggle-why') {
      const panel = document.getElementById(`why-panel-${index}`);
      panel.classList.toggle('open');
    }
  });
});
