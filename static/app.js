const chatWindow = document.getElementById("chat-window");
const input = document.getElementById("question-input");
const sendBtn = document.getElementById("send-btn");
const tableSelect = document.getElementById("table-select");

function addMessage(text, sender) {
  const div = document.createElement("div");
  div.className = `message ${sender}`;
  div.textContent = text;
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
      addMessage(data.answer, "agent");
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

loadTable("employees", "employees-table");
loadTable("departments", "departments-table");
loadTable("absences", "absences-table");
