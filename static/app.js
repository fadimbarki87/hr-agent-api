const chatWindow = document.getElementById("chat-window");
const input = document.getElementById("question-input");
const sendBtn = document.getElementById("send-btn");
const tableSelect = document.getElementById("table-select");
const examplesCard = document.querySelector(".examples-card");
const chatCard = document.querySelector(".chat-card");

function formatRouteLabel(routeName) {
  const routeLabels = {
    sql_only: "SQL only",
    review_semantic: "Semantic review search",
    review_semantic_plus_sql: "Semantic review search + SQL"
  };

  return routeLabels[routeName] || routeName || "Unknown";
}

function formatStatusLabel(status) {
  const statusLabels = {
    supported: "Answer returned",
    empty: "No matching rows",
    unsupported: "Unsupported or vague"
  };

  return statusLabels[status] || status || "Unknown";
}

function createEvidenceItem(label, value, options = {}) {
  const item = document.createElement("div");
  item.className = "evidence-item";

  const title = document.createElement("span");
  title.className = "evidence-label";
  title.textContent = label;

  const body = document.createElement("div");
  body.className = "evidence-value";

  if (options.badge) {
    const badge = document.createElement("span");
    badge.className = `evidence-badge ${options.badge}`;
    badge.textContent = value;
    body.appendChild(badge);
  } else {
    body.textContent = value;
  }

  item.append(title, body);
  return item;
}

function createEvidenceTableSection(title, tableData) {
  if (!tableData || !Array.isArray(tableData.columns) || !Array.isArray(tableData.rows)) {
    return null;
  }

  const section = document.createElement("section");
  section.className = "evidence-section";

  const heading = document.createElement("span");
  heading.className = "evidence-section-title";
  heading.textContent = `${title} (${tableData.row_count ?? tableData.rows.length})`;

  const wrap = document.createElement("div");
  wrap.className = "evidence-table-wrap";

  if (!tableData.rows.length) {
    const empty = document.createElement("div");
    empty.className = "evidence-empty";
    empty.textContent = "No rows to show for this step.";
    wrap.appendChild(empty);
    section.append(heading, wrap);
    return section;
  }

  const table = document.createElement("table");
  table.className = "evidence-table";

  const thead = document.createElement("thead");
  const tbody = document.createElement("tbody");
  const headerRow = document.createElement("tr");

  tableData.columns.forEach((column) => {
    const th = document.createElement("th");
    th.textContent = column;
    headerRow.appendChild(th);
  });

  thead.appendChild(headerRow);

  tableData.rows.forEach((row) => {
    const tr = document.createElement("tr");

    tableData.columns.forEach((column) => {
      const td = document.createElement("td");
      td.textContent = row[column] ?? "";
      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });

  table.append(thead, tbody);
  wrap.appendChild(table);
  section.append(heading, wrap);
  return section;
}

function createEvidenceCodeSection(title, content) {
  if (!content) {
    return null;
  }

  const section = document.createElement("section");
  section.className = "evidence-section";

  const heading = document.createElement("span");
  heading.className = "evidence-section-title";
  heading.textContent = title;

  const code = document.createElement("pre");
  code.className = "evidence-code";
  code.textContent = content;

  section.append(heading, code);
  return section;
}

function createEvidenceNotesSection(title, notes) {
  if (!Array.isArray(notes) || !notes.length) {
    return null;
  }

  const section = document.createElement("section");
  section.className = "evidence-section";

  const heading = document.createElement("span");
  heading.className = "evidence-section-title";
  heading.textContent = title;

  const list = document.createElement("ul");
  list.className = "evidence-notes";

  notes.forEach((note) => {
    const item = document.createElement("li");
    item.textContent = note;
    list.appendChild(item);
  });

  section.append(heading, list);
  return section;
}

function createEvidencePanel(evidence) {
  if (!evidence) {
    return null;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "evidence-block";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "evidence-toggle";
  button.setAttribute("aria-expanded", "false");
  button.textContent = "Evidence";

  const panel = document.createElement("div");
  panel.className = "evidence-panel";
  panel.hidden = true;

  const summary = document.createElement("div");
  summary.className = "evidence-grid";
  summary.append(
    createEvidenceItem("Outcome", formatStatusLabel(evidence.status), { badge: evidence.status || "unsupported" }),
    createEvidenceItem("Route used", formatRouteLabel(evidence.route_used)),
    createEvidenceItem("Normalized question", evidence.normalized_question || "")
  );

  if (evidence.route_requested && evidence.route_requested !== evidence.route_used) {
    summary.append(
      createEvidenceItem("Route requested", formatRouteLabel(evidence.route_requested))
    );
  }

  panel.appendChild(summary);

  if (evidence.reason) {
    panel.appendChild(createEvidenceItem("Explanation", evidence.reason));
  }

  const sqlSection = createEvidenceCodeSection("SQL query", evidence.sql);
  if (sqlSection) {
    panel.appendChild(sqlSection);
  }

  if (Array.isArray(evidence.semantic_candidate_ids) && evidence.semantic_candidate_ids.length) {
    panel.appendChild(
      createEvidenceItem(
        "Semantic candidate employee IDs",
        evidence.semantic_candidate_ids.join(", ")
      )
    );
  }

  const notesSection = createEvidenceNotesSection("Notes", evidence.notes);
  if (notesSection) {
    panel.appendChild(notesSection);
  }

  const semanticSection = createEvidenceTableSection(
    "Relevant review matches",
    evidence.semantic_matches
  );
  if (semanticSection) {
    panel.appendChild(semanticSection);
  }

  const resultSection = createEvidenceTableSection("Matching records", evidence.result);
  if (resultSection) {
    panel.appendChild(resultSection);
  }

  button.addEventListener("click", () => {
    const isOpen = !panel.hidden;
    panel.hidden = isOpen;
    button.textContent = isOpen ? "Evidence" : "Hide evidence";
    button.setAttribute("aria-expanded", String(!isOpen));
  });

  wrapper.append(button, panel);
  return wrapper;
}

function addMessage(text, sender, options = {}) {
  const div = document.createElement("div");
  div.className = `message ${sender}`;

  const body = document.createElement("div");
  body.className = "message-text";
  body.textContent = text;

  div.appendChild(body);

  if (sender === "agent" && options.evidence) {
    const evidencePanel = createEvidencePanel(options.evidence);
    if (evidencePanel) {
      div.appendChild(evidencePanel);
    }
  }

  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function sendQuestion() {
  const question = input.value.trim();
  if (!question) return;

  addMessage(question, "user");
  input.value = "";
  sendBtn.disabled = true;
  sendBtn.textContent = "Sending...";

  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        question: question,
        use_ai_formulation: true
      })
    });

    const data = await response.json();

    if (!response.ok) {
      addMessage(`Error: ${data.detail || "Something went wrong."}`, "agent");
    } else {
      addMessage(data.answer, "agent", { evidence: data.evidence });
    }
  } catch (error) {
    addMessage("Error: could not reach the server.", "agent");
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Send";
  }
}

sendBtn.addEventListener("click", sendQuestion);

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    sendQuestion();
  }
});

function focusChatInput() {
  if (!input) return;

  input.focus({ preventScroll: true });
  const inputLength = input.value.length;
  input.setSelectionRange(inputLength, inputLength);
}

function fillQuestionFromExample(questionText) {
  if (!input) return;

  input.value = questionText.trim();

  if (chatCard) {
    chatCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  window.setTimeout(focusChatInput, 220);
}

function prepareExampleQuestions() {
  if (!examplesCard) return;

  const exampleItems = examplesCard.querySelectorAll(".qa-group li");

  exampleItems.forEach((item) => {
    item.classList.add("example-question");
    item.tabIndex = 0;
    item.setAttribute("role", "button");
    item.setAttribute("aria-label", `Use example question: ${item.textContent.trim()}`);
  });

  examplesCard.addEventListener("click", (event) => {
    const questionItem = event.target.closest(".example-question");
    if (!questionItem || !examplesCard.contains(questionItem)) return;

    fillQuestionFromExample(questionItem.textContent);
  });

  examplesCard.addEventListener("keydown", (event) => {
    const questionItem = event.target.closest(".example-question");
    if (!questionItem || !examplesCard.contains(questionItem)) return;

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fillQuestionFromExample(questionItem.textContent);
    }
  });
}

function renderTable(containerId, columns, rows) {
  const container = document.getElementById(containerId);

  if (!rows || rows.length === 0) {
    container.innerHTML = '<div class="loading">No rows found.</div>';
    return;
  }

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const tbody = document.createElement("tbody");

  const headerRow = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach((col) => {
      const td = document.createElement("td");
      td.textContent = row[col] ?? "";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  table.appendChild(thead);
  table.appendChild(tbody);
  container.innerHTML = "";
  container.appendChild(table);
}

async function loadTable(tableName, containerId) {
  const container = document.getElementById(containerId);
  container.innerHTML = '<div class="loading">Loading table...</div>';

  try {
    const response = await fetch(`/data/${tableName}`);
    const data = await response.json();

    if (!response.ok) {
      container.innerHTML = `<div class="error">Failed to load ${tableName}.</div>`;
      return;
    }

    renderTable(containerId, data.columns, data.rows);
  } catch (error) {
    container.innerHTML = `<div class="error">Failed to load ${tableName}.</div>`;
  }
}

if (tableSelect) {
  tableSelect.addEventListener("change", (event) => {
    const targetId = event.target.value;
    if (!targetId) return;

    const target = document.getElementById(targetId);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
}

prepareExampleQuestions();
loadTable("employees", "employees-table");
loadTable("departments", "departments-table");
loadTable("absences", "absences-table");
