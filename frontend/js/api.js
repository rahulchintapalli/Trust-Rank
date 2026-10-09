/**
 * TrustRank API Client Module
 * Handles API fetch requests to the FastAPI backend.
 */

const API_BASE_URL = window.location.origin.includes(':8000') || window.location.origin.includes(':3000')
  ? 'http://localhost:8000'
  : window.location.origin;

/**
 * Executes POST /search to FastAPI backend.
 * @param {string} query Search input string
 * @param {number} topK Number of top results requested
 * @param {Object} weights 5-dimension weights object
 * @returns {Promise<Object>} API Response JSON
 */
async function searchAPI(query, topK = 10, weights = null) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 12000);

  try {
    const payload = {
      query: query.trim(),
      top_k: parseInt(topK, 10),
      weights: weights || {
        wRel: 0.25,
        wSup: 0.20,
        wFresh: 0.15,
        wCon: 0.20,
        wEvi: 0.20
      }
    };

    const response = await fetch(`${API_BASE_URL}/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`API HTTP Error ${response.status}: ${errText || response.statusText}`);
    }

    const data = await response.json();
    return data;

  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new Error('Search request timed out. Please try again.');
    }
    throw err;
  }
}
