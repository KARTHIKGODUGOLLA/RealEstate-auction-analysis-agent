const form = document.querySelector("#analysisForm");
const decisionCard = document.querySelector("#decisionCard");
const voiceButton = document.querySelector("#voiceButton");
const voiceStatus = document.querySelector("#voiceStatus");

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await analyze();
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

function render(analysis) {
  const rec = analysis.recommendation;
  const buying = analysis.buying_power;
  const hidden = analysis.hidden_costs;
  const rental = analysis.rental_yield;

  decisionCard.classList.remove("red", "yellow", "green");
  if (rec.category.toLowerCase().includes("red")) decisionCard.classList.add("red");
  if (rec.category.toLowerCase().includes("yellow")) decisionCard.classList.add("yellow");
  if (rec.category.toLowerCase().includes("green")) decisionCard.classList.add("green");

  document.querySelector("#recommendation").textContent = `${rec.category} · score ${rec.score}/100`;
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

function percent(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function setLoading(isLoading) {
  const button = form.querySelector("button[type='submit']");
  button.disabled = isLoading;
  button.textContent = isLoading ? "Analyzing..." : "Analyze auction";
}

analyze();
