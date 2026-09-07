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

  const isNeutral = job.interested === null;
  const isInterested = job.interested === 1;
  const isNotInterested = job.interested === 0;

  row.innerHTML = `
    <td class="role">${escapeHtml(job.role)}</td>
    <td class="company">${escapeHtml(job.company)}</td>
    <td class="location">${escapeHtml(job.location || "—")}</td>
    <td>${escapeHtml(job.experience || "—")}</td>
    <td class="date">${job.date || "—"}</td>
    <td>
      <div class="btn-group-vertical">
        <button class="btn-state neutral ${isNeutral ? 'active' : ''}" onclick="handleSetInterested(${job.id}, null)">?</button>
        <button class="btn-state interested ${isInterested ? 'active' : ''}" onclick="handleSetInterested(${job.id}, 1)">✓</button>
        <button class="btn-state not-interested ${isNotInterested ? 'active' : ''}" onclick="handleSetInterested(${job.id}, 0)">✗</button>
      </div>
    </td>
  `;

  return row;
}

/**
 * Set interested state for a job
 */
async function handleSetInterested(jobId, newState) {
  const row = document.querySelector(`[data-job-id="${jobId}"]`);
  const buttons = row.querySelectorAll(".btn-state");

  // Get current state
  let currentState = null;
  buttons.forEach(btn => {
    if (btn.classList.contains("active")) {
      if (btn.classList.contains("neutral")) currentState = null;
      else if (btn.classList.contains("interested")) currentState = 1;
      else if (btn.classList.contains("not-interested")) currentState = 0;
    }
  });

  // If already in desired state, don't do anything
  if (currentState === newState) return;

  // Optimistically update UI
  updateButtonStates(buttons, newState);
  buttons.forEach(btn => btn.disabled = true);

  try {
    const response = await fetch(`/api/jobs/${jobId}/interested`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ interested: newState })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    // Confirm server state and update UI
    updateButtonStates(buttons, data.interested);

    // Update stats
    loadStats();

  } catch (error) {
    console.error("Failed to update interested:", error);

    // Revert optimistic update
    updateButtonStates(buttons, currentState);
    showError(`Failed to update job ${jobId}`);

  } finally {
    buttons.forEach(btn => btn.disabled = false);
  }
}

function updateButtonStates(buttons, state) {
  // Clear all active states
  buttons.forEach(btn => btn.classList.remove("active"));

  // Set active state for the appropriate button
  buttons.forEach(btn => {
    if ((state === null && btn.classList.contains("neutral")) ||
        (state === 1 && btn.classList.contains("interested")) ||
        (state === 0 && btn.classList.contains("not-interested"))) {
      btn.classList.add("active");
    }
  });
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
