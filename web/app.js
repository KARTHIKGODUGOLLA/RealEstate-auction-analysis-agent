const form = document.querySelector("#analysisForm");
const decisionCard = document.querySelector("#decisionCard");
const voiceButton = document.querySelector("#voiceButton");
const voiceStatus = document.querySelector("#voiceStatus");
const propertySelect = document.querySelector("#propertySelect");
const rasaTranscript = document.querySelector("#rasaTranscript");
const rasaMessage = document.querySelector("#rasaMessage");
const rasaSend = document.querySelector("#rasaSend");

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await analyze();
});

rasaSend.addEventListener("click", async () => {
  await sendRasaMessage();
});

rasaMessage.addEventListener("keydown", async (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    await sendRasaMessage();
  }
});

propertySelect.addEventListener("change", () => {
  const selected = propertySelect.selectedOptions[0];
  if (!selected?.dataset.address) return;
  form.elements.address.value = selected.dataset.address.split(",")[0];
  form.elements.city.value = "Orlando";
  form.elements.currentBid.value = selected.dataset.currentBid || selected.dataset.minimumBid;
  form.elements.estimatedRepairs.value = "";
  form.elements.marketRent.value = "";
  analyze();
});

voiceButton.addEventListener("click", () => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    voiceStatus.textContent = "Voice input is not available in this browser. Use the text form for the demo.";
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.onstart = () => {
    voiceStatus.textContent = "Listening...";
  };
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    form.elements.prompt.value = transcript;
    voiceStatus.textContent = `Heard: "${transcript}"`;
  };
  recognition.onerror = () => {
    voiceStatus.textContent = "Voice input had trouble hearing that. Text fallback is ready.";
  };
  recognition.start();
});

async function analyze() {
  setLoading(true);
  const payload = Object.fromEntries(new FormData(form).entries());
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const analysis = await response.json();
  render(analysis);
  setLoading(false);
}

async function sendRasaMessage() {
  const message = rasaMessage.value.trim();
  if (!message) return;
  appendMessage("user", message);
  rasaMessage.value = "";
  rasaSend.disabled = true;
  rasaSend.textContent = "...";
  try {
    const response = await fetch("/api/rasa-chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sender: "web-demo", message }),
    });
    const payload = await response.json();
    if (payload.error) {
      appendMessage("error", `${payload.error}\n${payload.detail || ""}`.trim());
      return;
    }
    if (!payload.length) {
      appendMessage("agent", "Rasa returned no messages. It may be waiting for another turn.");
      return;
    }
    payload.forEach((item) => appendMessage("agent", item.text || JSON.stringify(item)));
  } catch (error) {
    appendMessage("error", `Could not reach the local Rasa proxy: ${error.message}`);
  } finally {
    rasaSend.disabled = false;
    rasaSend.textContent = "Send";
  }
}

function appendMessage(kind, text) {
  const bubble = document.createElement("div");
  bubble.className = `message ${kind}`;
  bubble.textContent = text;
  rasaTranscript.appendChild(bubble);
  rasaTranscript.scrollTop = rasaTranscript.scrollHeight;
}

async function loadProperties() {
  const response = await fetch("/api/properties");
  const payload = await response.json();
  payload.properties.forEach((property) => {
    const option = document.createElement("option");
    option.value = property.parcel_id;
    option.textContent = `${property.parcel_id} · ${property.address}`;
    option.dataset.address = property.address;
    option.dataset.currentBid = property.current_bid || "";
    option.dataset.minimumBid = property.minimum_bid || "";
    propertySelect.appendChild(option);
  });
}

function render(analysis) {
  const rec = analysis.recommendation;
  const buying = analysis.buying_power;
  const hidden = analysis.hidden_costs;
  const rental = analysis.rental_yield;
  const official = analysis.property_data.official_data_status;

  decisionCard.classList.remove("red", "yellow", "green");
  if (rec.category.toLowerCase().includes("red")) decisionCard.classList.add("red");
  if (rec.category.toLowerCase().includes("yellow")) decisionCard.classList.add("yellow");
  if (rec.category.toLowerCase().includes("green")) decisionCard.classList.add("green");

  document.querySelector("#recommendation").textContent = `${rec.category} · score ${rec.score}/100`;
  document.querySelector("#officialStatus").textContent =
    official?.status === "verified"
      ? "Official Treasury data verified live"
      : official?.status === "prepared_dataset"
        ? "Prepared multi-source auction dataset loaded"
        : "Using official-source fallback data";
  document.querySelector("#summary").textContent = rec.summary;
  document.querySelector("#maxBid").textContent = currency.format(rec.max_safe_bid);
  document.querySelector("#doNotBid").textContent = currency.format(rec.do_not_bid_above);

  document.querySelector("#buyingPower").textContent =
    `${buying.summary} Financing feasible: ${buying.financing_feasible ? "yes" : "no"}.`;
  document.querySelector("#hiddenCosts").textContent =
    `${hidden.summary} Biggest concern: ${rec.biggest_risk}.`;
  document.querySelector("#rentalYield").textContent =
    `At ${currency.format(rental.purchase_price)}, estimated cash flow is ${currency.format(rental.monthly_cash_flow)}/month, cap rate is ${percent(rental.cap_rate)}, and cash-on-cash is ${percent(rental.cash_on_cash_return)}.`;
  document.querySelector("#personalFit").textContent =
    `This is judged against a first-time auction buyer profile with limited cash and low tolerance for legal/title traps. ${rec.summary}`;

  const checklist = document.querySelector("#checklist");
  checklist.innerHTML = "";
  hidden.checklist.forEach((item) => {
    const row = document.createElement("article");
    row.className = "check-item";
    const status = item.status.replaceAll("_", " ");
    row.innerHTML = `
      <span class="status ${item.status.replaceAll("_", "-")}">${status}</span>
      <div>
        <h4>${item.source}</h4>
        <p>${item.finding}</p>
      </div>
    `;
    checklist.appendChild(row);
  });
}

async function loadSources() {
  const response = await fetch("/api/sources");
  const payload = await response.json();
  const sources = document.querySelector("#sources");
  sources.innerHTML = "";
  payload.sources.forEach((source) => {
    const item = document.createElement("article");
    item.className = "source-item";
    item.innerHTML = `
      <a href="${source.url}" target="_blank" rel="noreferrer">${source.name}</a>
      <p>${source.mode.replaceAll("_", " ")} · checks ${source.checks.join(", ")}</p>
    `;
    sources.appendChild(item);
  });
}

function percent(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function setLoading(isLoading) {
  const button = form.querySelector("button[type='submit']");
  button.disabled = isLoading;
  button.textContent = isLoading ? "Analyzing..." : "Analyze auction";
}

analyze();
loadSources();
loadProperties();
