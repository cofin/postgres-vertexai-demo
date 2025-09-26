// Simple Help Tooltips with HTMX

// Default to enabled for tech demo
let helpEnabled = localStorage.getItem("helpTooltipsEnabled") !== "false";
let activeTooltip = null;

// Toggle help mode
function toggleHelp() {
  helpEnabled = !helpEnabled;
  localStorage.setItem("helpTooltipsEnabled", helpEnabled.toString());

  // Update button text
  const button = document.querySelector(".help-toggle");
  if (button) {
    button.textContent = helpEnabled ? "✓" : "💡";
    button.classList.toggle("active", helpEnabled);
  }

  // Show/hide help elements
  document.querySelectorAll(".help-trigger").forEach((el) => {
    el.style.display = helpEnabled ? "inline-flex" : "none";
  });

  // Close any open tooltip
  hideTooltip();
}

// Initialize tooltip positioner
const tooltipPositioner = new TooltipPositioner({
  padding: 16,
  arrowSize: 10,
  preferredPlacements: {
    left: ["right", "left", "top", "bottom"],
    right: ["left", "right", "top", "bottom"],
  },
});

// Show tooltip
function showTooltip(triggerId, triggerElement) {
  hideTooltip();

  const tooltip = document.createElement("div");
  tooltip.className = "help-tooltip";
  tooltip.innerHTML = getTooltipHTML(triggerId);

  // NEW: Populate the skeleton with dynamic data
  populateTooltip(tooltip, triggerElement, triggerId);

  document.body.appendChild(tooltip);
  tooltip.style.visibility = "hidden";

  const position = tooltipPositioner.calculatePosition(triggerElement, tooltip);
  tooltip.style.left = position.left + "px";
  tooltip.style.top = position.top + "px";
  tooltip.setAttribute("data-placement", position.placement);

  tooltip.style.visibility = "visible";
  requestAnimationFrame(() => {
    tooltip.classList.add("show");
  });

  activeTooltip = tooltip;

  const closeBtn = tooltip.querySelector(".help-tooltip-close");
  if (closeBtn) {
    closeBtn.onclick = hideTooltip;
  }
}

// Hide tooltip
function hideTooltip() {
  if (activeTooltip) {
    activeTooltip.classList.remove("show");
    setTimeout(() => {
      activeTooltip?.remove();
      activeTooltip = null;
    }, 200);
  }
}

// Gets the HTML skeleton for a tooltip
function getTooltipHTML(triggerId) {
    const skeletons = {
        "intent-detection": {
            title: "🎯 Intent Detection",
            body: `
                <div class="help-tooltip-section">
                    <div class="help-tooltip-section-title">PostgreSQL pgvector Query</div>
                    <pre><code class="sql-query-placeholder">-- Populated from backend</code></pre>
                </div>
                <div class="help-tooltip-section">
                    <div class="help-tooltip-section-title">Detection Results</div>
                    <div class="help-tooltip-metric">
                        <span class="help-tooltip-metric-label">Detected Intent</span>
                        <span class="help-tooltip-metric-value intent-name-placeholder">N/A</span>
                    </div>
                    <div class="help-tooltip-metric">
                        <span class="help-tooltip-metric-label">Confidence</span>
                        <span class="help-tooltip-metric-value confidence-placeholder">N/A</span>
                    </div>
                </div>
            `
        },
        "vector-search": {
            title: "🔍 Product Vector Search",
            body: `
                <div class="help-tooltip-section">
                    <div class="help-tooltip-section-title">PostgreSQL pgvector Query</div>
                    <pre><code class="sql-query-placeholder">-- Populated from backend</code></pre>
                </div>
                <div class="help-tooltip-section">
                    <div class="help-tooltip-section-title">Search Results</div>
                    <div class="help-tooltip-metric">
                        <span class="help-tooltip-metric-label">Results Found</span>
                        <span class="help-tooltip-metric-value results-count-placeholder">N/A</span>
                    </div>
                </div>
            `
        },
        "performance-summary": {
            title: "📊 Performance Breakdown",
            body: `
                <div class="help-tooltip-section perf-chart">
                    <div class="perf-bar">
                        <div class="perf-bar-label">Total Time</div>
                        <div class="perf-bar-track">
                            <div class="perf-bar-fill total-time-bar" style="width: 100%;"></div>
                        </div>
                        <div class="perf-bar-value total-time-value">N/A</div>
                    </div>
                    <!-- More bars can be added dynamically -->
                </div>
            `
        },
        // ... other static tooltips
    };

    const skeleton = skeletons[triggerId] || { title: "Details", body: "<p>No details available for this component.</p>" };

    return `
        <div class="help-tooltip-content">
            <div class="help-tooltip-header">
                <h3 class="help-tooltip-title">${skeleton.title}</h3>
                <button class="help-tooltip-close" type="button">×</button>
            </div>
            <div class="help-tooltip-body">${skeleton.body}</div>
        </div>
    `;
}

// Populates the tooltip skeleton with live data
function populateTooltip(tooltipElement, triggerElement, triggerId) {
    const debugInfo = JSON.parse(triggerElement.dataset.debugInfo || '{}');

    if (triggerId === 'intent-detection' && debugInfo.intent) {
        const queryElem = tooltipElement.querySelector('.sql-query-placeholder');
        if (queryElem) {
            queryElem.textContent = `SELECT\n    intent, phrase, 1 - (embedding <=> :query_embedding) AS similarity\nFROM intent_exemplar\nWHERE 1 - (embedding <=> :query_embedding) > :min_threshold\nORDER BY similarity DESC\nLIMIT :limit;`;
        }
        tooltipElement.querySelector('.intent-name-placeholder').textContent = debugInfo.intent.intent || 'N/A';
        tooltipElement.querySelector('.confidence-placeholder').textContent = `${((debugInfo.intent.confidence || 0) * 100).toFixed(1)}%`;
    }

    if (triggerId === 'vector-search' && debugInfo.search) {
        const queryElem = tooltipElement.querySelector('.sql-query-placeholder');
        if (queryElem) {
            queryElem.textContent = `SELECT\n    name, description, 1 - (embedding <=> :query_embedding) AS similarity_score\nFROM product\nWHERE in_stock = true AND 1 - (embedding <=> :query_embedding) >= :similarity_threshold\nORDER BY embedding <=> :query_embedding\nLIMIT :limit_count;`;
        }
        tooltipElement.querySelector('.results-count-placeholder').textContent = debugInfo.search.results_count || 0;
    }

    if (triggerId === 'performance-summary' && debugInfo.timings) {
        const totalTime = debugInfo.timings.total_ms || 0;
        tooltipElement.querySelector('.total-time-value').textContent = `${totalTime}ms`;
    }
}

// Initialize on load
document.addEventListener("DOMContentLoaded", () => {
  const button = document.querySelector(".help-toggle");
  if (button) {
    button.textContent = helpEnabled ? "✓" : "💡";
    button.classList.toggle("active", helpEnabled);
  }
  document.querySelectorAll(".help-trigger").forEach((el) => {
    el.style.display = helpEnabled ? "inline-flex" : "none";
  });
});

// Handle clicks outside tooltips
document.addEventListener("click", (e) => {
  if (activeTooltip && !activeTooltip.contains(e.target) && !e.target.closest(".help-trigger")) {
    hideTooltip();
  }
});

// Handle HTMX events
document.body.addEventListener("htmx:afterRequest", () => {
  setTimeout(() => {
    document.querySelectorAll(".help-trigger").forEach((el) => {
      el.style.display = helpEnabled ? "inline-flex" : "none";
    });
  }, 100);
});
