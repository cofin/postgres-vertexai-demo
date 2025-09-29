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
                <div class="help-tooltip-section">
                    <div class="help-tooltip-section-title">Total Response Time</div>
                    <div class="help-tooltip-metric">
                        <span class="help-tooltip-metric-label">Total Time</span>
                        <span class="help-tooltip-metric-value total-time-value">N/A</span>
                    </div>
                </div>
                <div class="help-tooltip-section perf-chart">
                    <div class="help-tooltip-section-title">Component Breakdown</div>
                    <!-- Performance bars will be populated dynamically -->
                </div>
            `
        },
        "response-cache-hit": {
            title: "⚡ Response Cache Hit",
            body: `
                <div class="help-tooltip-section">
                    <div class="help-tooltip-section-title">Cache Details</div>
                    <p>This response was served from the response cache, providing faster delivery without re-processing the query through the ADK agents.</p>
                    <div class="help-tooltip-metric">
                        <span class="help-tooltip-metric-label">Response Time</span>
                        <span class="help-tooltip-metric-value">~5ms (cached)</span>
                    </div>
                </div>
            `
        },
        "embedding-cache-hit": {
            title: "🧠 Embedding Cache Hit",
            body: `
                <div class="help-tooltip-section">
                    <div class="help-tooltip-section-title">Embedding Cache Details</div>
                    <p>The text embedding for this query was served from cache, avoiding a round-trip to Vertex AI.</p>
                    <div class="help-tooltip-metric">
                        <span class="help-tooltip-metric-label">Embedding Time</span>
                        <span class="help-tooltip-metric-value">~1ms (cached)</span>
                    </div>
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
    if (triggerId === 'intent-detection') {
        const intent = triggerElement.dataset.intent || 'UNKNOWN';
        const confidence = parseFloat(triggerElement.dataset.confidence || 0);
        const sql = triggerElement.dataset.sql;

        const queryElem = tooltipElement.querySelector('.sql-query-placeholder');
        if (queryElem) {
            queryElem.textContent = sql || `WITH
    query_embedding AS (
        SELECT
            intent,
            phrase,
            1 - (embedding <=> $1) AS similarity,
            confidence_threshold,
            usage_count
        FROM intent_exemplar
    )
SELECT
    intent,
    phrase,
    similarity,
    confidence_threshold,
    usage_count
FROM query_embedding
WHERE similarity > $2
ORDER BY similarity DESC
LIMIT $3`;
        }

        const intentElem = tooltipElement.querySelector('.intent-name-placeholder');
        if (intentElem) intentElem.textContent = intent;

        const confidenceElem = tooltipElement.querySelector('.confidence-placeholder');
        if (confidenceElem) confidenceElem.textContent = `${(confidence * 100).toFixed(1)}%`;
    }

    if (triggerId === 'vector-search') {
        const sql = triggerElement.dataset.sql;
        const results = triggerElement.dataset.results || 0;
        const params = JSON.parse(triggerElement.dataset.params || '{}');

        const queryElem = tooltipElement.querySelector('.sql-query-placeholder');
        if (queryElem && sql) {
            queryElem.textContent = sql;
        }

        const resultsElem = tooltipElement.querySelector('.results-count-placeholder');
        if (resultsElem) resultsElem.textContent = results;

        const paramsElem = tooltipElement.querySelector('.params-placeholder');
        if (paramsElem) paramsElem.textContent = JSON.stringify(params, null, 2);
    }

    if (triggerId === 'performance-summary') {
        const timingsStr = triggerElement.dataset.timings;
        if (timingsStr) {
            try {
                const timings = JSON.parse(timingsStr);
                updatePerformanceTooltipContent(tooltipElement, timings);
            } catch (e) {
                console.error('Error parsing timings:', e);
            }
        }
    }
}

// Update performance tooltip content with detailed breakdown
function updatePerformanceTooltipContent(tooltipElement, timings) {
    const chartEl = tooltipElement.querySelector('.perf-chart');
    if (!chartEl) return;

    // Build performance bars for each component
    const components = [
        { label: "Agent Processing", value: timings.agent_processing_ms || 0, color: "#f59e0b" },
        { label: "Intent Classification", value: timings.intent_classification_ms || 0, color: "#10b981" },
        { label: "Vector Search", value: timings.vector_search_ms || 0, color: "#8b5cf6" },
        { label: "Embedding Generation", value: timings.embedding_generation_ms || 0, color: "#f97316" },
        { label: "Session Management", value: timings.session_ms || 0, color: "#6366f1" },
    ];

    const totalTime = timings.total_ms || 0;
    const maxTime = Math.max(...components.map(c => c.value), totalTime, 1);

    const barsHtml = components
        .filter(c => c.value > 0)
        .map(comp => `
            <div class="perf-bar">
                <div class="perf-bar-label">${comp.label}</div>
                <div class="perf-bar-track">
                    <div class="perf-bar-fill" style="width: ${(comp.value / maxTime) * 100}%; background: ${comp.color}"></div>
                </div>
                <div class="perf-bar-value">${comp.value}ms</div>
            </div>
        `).join("");

    chartEl.innerHTML = barsHtml;

    // Update total time if there's a separate total element
    const totalValueElem = tooltipElement.querySelector('.total-time-value');
    if (totalValueElem) {
        totalValueElem.textContent = `${totalTime}ms`;
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
