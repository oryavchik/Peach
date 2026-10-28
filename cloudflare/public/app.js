const $ = id => document.getElementById(id);
const empty = () => ({ title: null, starts_at: null, duration_minutes: null, items: [], action_items: [], language: "uk" });
let selected = null, agenda = empty(), original = null, marked = new Set(), controller = null;
function error(message = "") { $("error").textContent = message; $("error").hidden = !message; }
async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options,
    headers: { "Content-Type": "application/json", ...options.headers } });
  const value = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) show(false);
    throw new Error(value.error || "Сервіс не відповідає. Спробуй ще.");
  }
  return value;
}
function show(signedIn) { $("login").hidden = signedIn; $("workspace").hidden = !signedIn; $("logout").hidden = !signedIn; }
async function list() {
  const { items } = await api("/api/meetings");
  $("meetings").replaceChildren(...items.map(item => {
    const button = document.createElement("button"); button.type = "button";
    button.className = "meeting" + (selected === item.id ? " active" : ""); button.textContent = item.title;
    button.onclick = () => open(item.id).catch(e => error(e.message)); return button;
  }));
}
function touch(path, label) {
  marked.delete(path); label.querySelector(".badge")?.remove(); $("saved").textContent = "";
}
function badge(label, path) {
  label.querySelector(".badge")?.remove();
  if (marked.has(path)) { const span = document.createElement("span"); span.className = "badge"; span.textContent = "suggested"; label.append(span); }
}
function render() {
  document.querySelectorAll("[data-field]").forEach(input => {
    const path = input.dataset.field; input.value = agenda[path] ?? ""; badge(input.parentElement, path);
    input.oninput = () => { agenda[path] = input.value === "" ? null : path === "duration_minutes" ? Number(input.value) : input.value; touch(path, input.parentElement); };
  });
  rows("items", $("items"), [{key:"topic",name:"Тема"},{key:"owner",name:"Відповідальний"},{key:"minutes",name:"Хвилини",type:"number"}]);
  rows("action_items", $("action-items"), [{key:"task",name:"Задача"},{key:"owner",name:"Відповідальний"},{key:"due",name:"До",type:"date"}]);
  $("provenance").hidden = !original; $("original").textContent = original ? JSON.stringify(original, null, 2) : "";
}
function rows(group, container, fields) {
  container.replaceChildren(...agenda[group].map((row, index) => {
    const div = document.createElement("div"); div.className = "row" + (group === "action_items" ? " action" : "");
    for (const field of fields) {
      const path = `${group}.${index}.${field.key}`, label = document.createElement("label"); label.append(document.createTextNode(field.name));
      const input = document.createElement("input"); input.type = field.type || "text"; input.value = row[field.key] ?? "";
      if (field.type === "number") { input.min = "1"; input.max = "480"; }
      if (field.key === "topic" || field.key === "task") input.required = true;
      input.oninput = () => { row[field.key] = input.value === "" ? null : field.type === "number" ? Number(input.value) : input.value; touch(path, label); };
      label.append(input); badge(label, path); div.append(label);
    }
    const remove = document.createElement("button"); remove.type = "button"; remove.className = "remove"; remove.textContent = "×"; remove.setAttribute("aria-label", "Видалити рядок");
    remove.onclick = () => { agenda[group].splice(index, 1); const next = new Set();
      for (const path of marked) { const [g, i, key] = path.split("."); if (g !== group) next.add(path); else if (+i !== index) next.add(`${g}.${+i > index ? +i - 1 : i}.${key}`); }
      marked = next; $("saved").textContent = ""; render(); };
    div.append(remove); return div;
  }));
}
function busy(value) { $("parse").disabled = value; $("cancel").hidden = !value; $("progress").textContent = value ? "AI готує пропозицію…" : ""; }
async function open(id) {
  controller?.abort(); controller = null; busy(false); error();
  const value = await api(`/api/meetings/${id}/agenda`); selected = id;
  agenda = value.agenda || empty(); original = value.ai_suggestion; marked = new Set();
  $("selected-title").textContent = value.title; $("choose").hidden = true; $("editing").hidden = false;
  $("pasted").value = ""; $("saved").textContent = ""; render(); await list();
}
$("login-form").onsubmit = async event => { event.preventDefault(); error();
  try { await api("/api/login", { method: "POST", body: JSON.stringify({ password: $("password").value }) }); $("password").value = ""; show(true); await list(); }
  catch(e) { error(e.message); }
};
$("logout").onclick = async () => { controller?.abort(); await api("/api/logout", { method: "POST", body: "{}" }); show(false); };
$("new-meeting").onsubmit = async event => { event.preventDefault(); error();
  try { const value = await api("/api/meetings", { method: "POST", body: JSON.stringify({ title: $("meeting-title").value }) }); $("meeting-title").value = ""; await open(value.id); }
  catch(e) { error(e.message); }
};
$("parse").onclick = async () => {
  const active = new AbortController(), meeting = selected; controller = active; busy(true); error(); $("saved").textContent = "";
  const now = new Date(), today = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
  try {
    const result = await api("/api/parse", { method: "POST", signal: active.signal, body: JSON.stringify({ text: $("pasted").value, today, tz: Intl.DateTimeFormat().resolvedOptions().timeZone }) });
    if (active.signal.aborted || meeting !== selected) return;
    original = structuredClone(result); agenda = structuredClone(result.agenda); marked = new Set();
    for (const field of ["title","starts_at","duration_minutes","language"]) if (agenda[field] != null) marked.add(field);
    for (const group of ["items","action_items"]) agenda[group].forEach((row,i) => Object.entries(row).forEach(([field,value]) => { if (value != null) marked.add(`${group}.${i}.${field}`); }));
    render();
  } catch(e) { if (!active.signal.aborted) error(e.message); }
  finally { if (controller === active) { controller = null; busy(false); } }
};
$("cancel").onclick = () => { controller?.abort(); controller = null; busy(false); $("progress").textContent = "Очікування скасовано. Запит моделі міг уже початися."; };
$("add-item").onclick = () => { agenda.items.push({topic:"",owner:null,minutes:null}); render(); };
$("add-action").onclick = () => { agenda.action_items.push({task:"",owner:null,due:null}); render(); };
$("agenda-form").onsubmit = async event => { event.preventDefault(); error(); $("save").disabled = true;
  try { await api(`/api/meetings/${selected}/agenda`, { method:"POST", body:JSON.stringify({agenda,ai_suggestion:original}) }); $("saved").textContent = "Agenda збережено ✓"; await list(); }
  catch(e) { error(e.message); } finally { $("save").disabled = false; }
};
(async () => { try { await api("/api/me"); show(true); await list(); } catch { show(false); } })();
