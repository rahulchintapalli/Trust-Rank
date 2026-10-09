/**
 * Main Application Controller for TrustRank Frontend
 * Manages search execution, filtering, sorting, report export, custom claim ingestion, and voting.
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
  const filterBar = document.getElementById('filter-bar');
  const analyticsSection = document.getElementById('analytics-section');
  const analyticsContainer = document.getElementById('analytics-container');
  const sortSelect = document.getElementById('sort-select');
  const exportBtn = document.getElementById('export-btn');

  // Modal Elements
  const openIngestBtn = document.getElementById('open-ingest-btn');
  const closeIngestBtn = document.getElementById('close-ingest-btn');
  const ingestModal = document.getElementById('ingest-modal');
  const ingestForm = document.getElementById('ingest-form');

  // Slider Elements
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

  // State Store
  let currentRawResults = [];
  let currentAnalytics = {};
  let currentQuery = '';
  let activeFilter = 'all';

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
     2. OPTIONS & SLIDERS
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
     3. LIVE FILTERING & SORTING LOGIC
     ============================================ */
  function renderFilteredAndSortedResults() {
    if (!currentRawResults || currentRawResults.length === 0) {
      resultsGrid.innerHTML = renderEmptyState(currentQuery);
      return;
    }

    // Apply Source Type Filter
    let filtered = currentRawResults;
    if (activeFilter !== 'all') {
      filtered = currentRawResults.filter(r => {
        const sType = (r.source_type || r.sourceType || '').toLowerCase();
        return sType.includes(activeFilter);
      });
    }

    // Apply Sorting
    const sortKey = sortSelect.value;
    const sorted = [...filtered].sort((a, b) => {
      const sA = a.scores || {};
      const sB = b.scores || {};
      if (sortKey === 'relevance') return (sB.relevance || 0) - (sA.relevance || 0);
      if (sortKey === 'reliability') return (sB.reliability || 0) - (sA.reliability || 0);
      if (sortKey === 'freshness') return (sB.freshness || 0) - (sA.freshness || 0);
      return (sB.composite || a.trust_rank_score || 0) - (sA.composite || b.trust_rank_score || 0);
    });

    if (sorted.length === 0) {
      resultsGrid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--text-muted);">No documents match filter "${activeFilter}".</div>`;
    } else {
      resultsGrid.innerHTML = sorted.map((res, i) => renderResultCard(res, i)).join('');
      animateScoreVisuals(resultsGrid);
    }
  }

  // Filter Pills Event Handling
  document.querySelectorAll('.filter-pill').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      activeFilter = e.target.dataset.filter;
      renderFilteredAndSortedResults();
    });
  });

  sortSelect.addEventListener('change', renderFilteredAndSortedResults);

  /* ============================================
     4. SEARCH EXECUTION
     ============================================ */
  searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;

    currentQuery = query;
    const topK = parseInt(topKInput.value, 10);
    const weights = getSliderWeights();

    searchBtn.disabled = true;
    searchBtn.innerHTML = `<div class="spinner"></div> Searching...`;
    resultsGrid.innerHTML = renderSkeletons(topK > 6 ? 6 : topK);
    resultsMetaBar.style.display = 'none';
    analyticsSection.style.display = 'none';
    filterBar.style.display = 'none';

    try {
      const data = await searchAPI(query, topK, weights);
      currentRawResults = data.results || [];
      currentAnalytics = data.analytics || {};
      const totalCandidates = data.total_candidates ?? currentRawResults.length;
      const queryTimeMs = data.query_time_ms ?? 10;

      if (!currentRawResults || currentRawResults.length === 0) {
        resultsGrid.innerHTML = renderEmptyState(query);
      } else {
        // Show Analytics Synthesis Banner & Filter Controls
        analyticsSection.style.display = 'block';
        analyticsContainer.innerHTML = renderAnalyticsBanner(currentAnalytics, currentRawResults.length);
        filterBar.style.display = 'flex';

        resultsMetaBar.style.display = 'flex';
        const flaggedCount = currentRawResults.filter(r => r.contradiction_alert || r.contradictionAlert).length;
        resultsMetaBar.innerHTML = `
          <div>Evaluated <strong>${totalCandidates}</strong> candidate claims in ${queryTimeMs}ms</div>
          <div>${flaggedCount > 0 ? `<span style="color: var(--danger-red); font-weight: 700;">⚠️ ${flaggedCount} contradiction alert(s)</span>` : '✅ High peer consistency'}</div>
        `;

        renderFilteredAndSortedResults();
      }

    } catch (err) {
      console.error('[TrustRank App Error]:', err);
      resultsGrid.innerHTML = renderErrorState(err.message || 'Failed to connect to TrustRank backend.');
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
     5. REPORT EXPORT (JSON / Markdown)
     ============================================ */
  exportBtn.addEventListener('click', () => {
    if (!currentRawResults || currentRawResults.length === 0) return;

    const reportData = {
      title: "TrustRank Reliable Search Report",
      query: currentQuery,
      timestamp: new Date().toISOString(),
      analytics: currentAnalytics,
      results: currentRawResults
    };

    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `TrustRank_Report_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });

  /* ============================================
     6. CUSTOM CLAIM INGESTION MODAL
     ============================================ */
  openIngestBtn.addEventListener('click', () => ingestModal.style.display = 'flex');
  closeIngestBtn.addEventListener('click', () => ingestModal.style.display = 'none');

  ingestForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = document.getElementById('ingest-text').value.trim();
    const source = document.getElementById('ingest-source').value.trim();
    const sType = document.getElementById('ingest-type').value;

    if (!text || !source) return;

    const docId = `custom_${Date.now()}`;
    const payload = {
      documents: [{
        id: docId,
        text: text,
        source: source,
        source_type: sType,
        evidence_type: sType.toLowerCase().includes('academic') ? 'peer-reviewed' : 'news',
        timestamp: new Date().toISOString(),
        category: 'vital signs'
      }]
    };

    try {
      const resp = await fetch('http://localhost:8000/seed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (resp.ok) {
        alert('✅ Document indexed successfully into TrustRank Vector Store!');
        ingestModal.style.display = 'none';
        ingestForm.reset();
      }
    } catch (e) {
      alert('Error indexing custom claim: ' + e.message);
    }
  });

  /* ============================================
     7. CARD INTERACTION DELEGATION (Vote / Copy Citation)
     ============================================ */
  resultsGrid.addEventListener('click', async (e) => {
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
    } else if (action === 'copy-citation') {
      const citationText = target.dataset.citation;
      navigator.clipboard.writeText(citationText);
      target.textContent = '✅ Copied!';
      setTimeout(() => target.textContent = '📋 Copy APA Citation', 2000);
    } else if (action === 'vote') {
      const voteType = target.dataset.vote;
      const docId = target.dataset.docId;
      try {
        await fetch('http://localhost:8000/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ doc_id: docId, vote: voteType })
        });
        target.style.background = 'var(--primary-blue-light)';
        target.style.color = 'var(--primary-blue)';
        target.disabled = true;
      } catch (err) {
        console.warn('Feedback error:', err);
      }
    }
  });
});
