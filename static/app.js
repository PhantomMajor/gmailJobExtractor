/**
 * Job Dashboard Client
 * Handles job fetching, filtering, and interested toggle
 */

let currentFilter = { company: "", interested: false };
let allJobs = [];
let filterTimeout;

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  loadStats();
  loadJobs();
  setupEventListeners();
});

/**
 * Set up event listeners for filters and buttons
 */
function setupEventListeners() {
  const companyInput = document.getElementById("company-filter");
  const btnAll = document.getElementById("btn-all");
  const btnInterested = document.getElementById("btn-interested");

  // Company filter with debounce
  companyInput.addEventListener("input", (e) => {
    clearTimeout(filterTimeout);
    filterTimeout = setTimeout(() => {
      currentFilter.company = e.target.value.trim();
      loadJobs();
    }, 300);
  });

  // Filter toggles
  btnAll.addEventListener("click", () => {
    currentFilter.interested = false;
    currentFilter.company = document.getElementById("company-filter").value.trim();
    btnAll.classList.add("active");
    btnInterested.classList.remove("active");
    loadJobs();
  });

  btnInterested.addEventListener("click", () => {
    currentFilter.interested = true;
    currentFilter.company = document.getElementById("company-filter").value.trim();
    btnInterested.classList.add("active");
    btnAll.classList.remove("active");
    loadJobs();
  });
}

/**
 * Fetch jobs from API with current filters
 */
async function loadJobs() {
  try {
    const params = new URLSearchParams();
    if (currentFilter.company) {
      params.append("company", currentFilter.company);
    }
    if (currentFilter.interested) {
      params.append("interested", "1");
    }

    const response = await fetch(`/api/jobs?${params}`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    allJobs = data.jobs || [];
    renderJobs(allJobs);
    clearError();

  } catch (error) {
    console.error("Failed to load jobs:", error);
    showError("Failed to load jobs. Please refresh the page.");
  }
}

/**
 * Render jobs table with current data
 */
function renderJobs(jobs) {
  const tbody = document.getElementById("jobs-tbody");
  const table = document.getElementById("jobs-table");
  const loading = document.getElementById("loading");
  const emptyState = document.getElementById("empty-state");

  loading.style.display = "none";

  if (jobs.length === 0) {
    table.style.display = "none";
    emptyState.style.display = "block";
    return;
  }

  tbody.innerHTML = "";
  jobs.forEach((job) => {
    const row = createJobRow(job);
    tbody.appendChild(row);
  });

  table.style.display = "table";
  emptyState.style.display = "none";
}

/**
 * Create a table row for a single job
 */
function createJobRow(job) {
  const row = document.createElement("tr");
  row.setAttribute("data-job-id", job.id);

  // Get button text and class based on state: null, 1, or 0
  let buttonText, buttonClass;
  if (job.interested === null) {
    buttonText = "? Not Evaluated";
    buttonClass = "btn-interested";
  } else if (job.interested === 1) {
    buttonText = "✓ Interested";
    buttonClass = "btn-interested interested";
  } else { // job.interested === 0
    buttonText = "✗ Not Interested";
    buttonClass = "btn-interested not-interested";
  }

  row.innerHTML = `
    <td class="role">${escapeHtml(job.role)}</td>
    <td class="company">${escapeHtml(job.company)}</td>
    <td class="location">${escapeHtml(job.location || "—")}</td>
    <td>${escapeHtml(job.experience || "—")}</td>
    <td class="date">${job.date || "—"}</td>
    <td>
      <button class="${buttonClass}" onclick="handleToggleInterested(${job.id})">
        ${buttonText}
      </button>
    </td>
  `;

  return row;
}

/**
 * Toggle interested flag for a job
 */
async function handleToggleInterested(jobId) {
  const row = document.querySelector(`[data-job-id="${jobId}"]`);
  const button = row.querySelector(".btn-interested");

  // Get current state from button classes
  let currentState;
  if (button.classList.contains("interested")) {
    currentState = 1; // Interested
  } else if (button.classList.contains("not-interested")) {
    currentState = 0; // Not Interested
  } else {
    currentState = null; // Not Evaluated
  }

  // Predict next state (optimistic update)
  // Cycle: null -> 1 -> 0 -> 1 -> 0 -> ... (never back to null once touched)
  let nextState;
  if (currentState === null) {
    nextState = 1; // null -> 1 (Interested, first touch)
  } else if (currentState === 1) {
    nextState = 0; // 1 -> 0 (Not Interested)
  } else {
    nextState = 1; // 0 -> 1 (Interested)
  }

  // Optimistically update UI
  updateButtonState(button, nextState);
  button.disabled = true;

  try {
    const response = await fetch(`/api/jobs/${jobId}/interested`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    // Confirm server state and update UI
    updateButtonState(button, data.interested);

    // Update stats
    loadStats();

  } catch (error) {
    console.error("Failed to toggle interested:", error);

    // Revert optimistic update
    updateButtonState(button, currentState);
    showError(`Failed to update job ${jobId}`);

  } finally {
    button.disabled = false;
  }
}

function updateButtonState(button, state) {
  // Update button text and classes based on state
  button.classList.remove("interested", "not-interested");

  if (state === null) {
    button.textContent = "? Not Evaluated";
    // No special class for not-evaluated (default gray)
  } else if (state === 1) {
    button.textContent = "✓ Interested";
    button.classList.add("interested");
  } else { // state === 0
    button.textContent = "✗ Not Interested";
    button.classList.add("not-interested");
  }
}

/**
 * Load and display statistics
 */
async function loadStats() {
  try {
    const response = await fetch("/api/stats");

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const stats = await response.json();

    document.getElementById("stat-total").textContent = stats.total_jobs || 0;
    document.getElementById("stat-companies").textContent = stats.unique_companies || 0;
    document.getElementById("stat-interested").textContent = stats.interested_count || 0;

  } catch (error) {
    console.error("Failed to load stats:", error);
  }
}

/**
 * Display error message
 */
function showError(message) {
  const errorContainer = document.getElementById("error-container");
  errorContainer.innerHTML = `<div class="error">${escapeHtml(message)}</div>`;
}

/**
 * Clear error message
 */
function clearError() {
  const errorContainer = document.getElementById("error-container");
  errorContainer.innerHTML = "";
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
