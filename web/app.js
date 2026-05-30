const form = document.querySelector("#analysisForm");
const decisionCard = document.querySelector("#decisionCard");
const voiceButton = document.querySelector("#voiceButton");
const voiceReplyToggle = document.querySelector("#voiceReplyToggle");
const voiceStatus = document.querySelector("#voiceStatus");
const testVoice = document.querySelector("#testVoice");
const propertySelect = document.querySelector("#propertySelect");
const propertySummary = document.querySelector("#propertySummary");
const rasaTranscript = document.querySelector("#rasaTranscript");
const rasaMessage = document.querySelector("#rasaMessage");
const rasaSend = document.querySelector("#rasaSend");
const clearChat = document.querySelector("#clearChat");
const askDecision = document.querySelector("#askDecision");
const askRisks = document.querySelector("#askRisks");
const askMaxBid = document.querySelector("#askMaxBid");
const pitchMode = document.querySelector("#pitchMode");
const bestFit = document.querySelector("#bestFit");
const biggestTrap = document.querySelector("#biggestTrap");

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

let voiceRepliesEnabled = true;
let selectedVoice = null;
let speechQueue = [];
let speechActive = false;
let currentThinkingBubble = null;
let replyAudio = new Audio();
let primedAudio = false;
let chatBusy = false;
const openingMessage = "Pick a property and ask for the call. I will keep the answer short enough to hear.";

hydrateVoiceControls();
hydrateVoiceInputControls();

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  unlockSpeech();
  await analyze({ speakResult: true });
});

voiceReplyToggle.addEventListener("click", () => {
  unlockSpeech();
  voiceRepliesEnabled = !voiceRepliesEnabled;
  if (!voiceRepliesEnabled) {
    stopSpeaking();
  }
  voiceReplyToggle.textContent = voiceRepliesEnabled ? "Voice replies on" : "Voice replies off";
  voiceReplyToggle.setAttribute("aria-pressed", String(voiceRepliesEnabled));
  voiceStatus.textContent = voiceRepliesEnabled
    ? "Voice replies are on."
    : "Voice replies are off. Text chat still works.";
});

testVoice.addEventListener("click", () => {
  unlockSpeech();
  voiceRepliesEnabled = true;
  voiceReplyToggle.textContent = "Voice replies on";
  voiceReplyToggle.setAttribute("aria-pressed", "true");
  speak("Voice is on. Ask for the bid call when you're ready.");
});

clearChat.addEventListener("click", () => {
  stopSpeaking();
  rasaTranscript.innerHTML = "";
  appendMessage("agent", openingMessage);
  rasaMessage.value = "";
  rasaMessage.focus();
  voiceStatus.textContent = "Chat cleared. Ready for the next question.";
});

rasaSend.addEventListener("click", async () => {
  unlockSpeech();
  await sendRasaMessage();
});

rasaMessage.addEventListener("keydown", async (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    await sendRasaMessage();
  }
});

askDecision.addEventListener("click", async () => {
  unlockSpeech();
  await sendRasaMessage("Should I bid on the selected property?");
});

askRisks.addEventListener("click", async () => {
  unlockSpeech();
  await sendRasaMessage("What could go wrong with this auction property?");
});

askMaxBid.addEventListener("click", async () => {
  unlockSpeech();
  await sendRasaMessage("Explain my maximum safe bid for this property.");
});

pitchMode.addEventListener("click", async () => {
  unlockSpeech();
  await runPitchMode();
});

bestFit.addEventListener("click", async () => {
  unlockSpeech();
  await applySpotlight("best_fit");
});

biggestTrap.addEventListener("click", async () => {
  unlockSpeech();
  await applySpotlight("biggest_trap");
});

propertySelect.addEventListener("change", () => {
  const selected = propertySelect.selectedOptions[0];
  const selectedDeal = normalizeSelectedDeal(selected);
  form.elements.address.value = selectedDeal.address.split(",")[0];
  form.elements.city.value = "Orlando";
  form.elements.currentBid.value = selectedDeal.currentBid;
  form.elements.estimatedRepairs.value = "";
  form.elements.marketRent.value = "";
  renderPropertySummary(selectedDeal);
  resetChatForSelection(selectedDeal);
  analyze();
});

voiceButton.addEventListener("click", () => {
  unlockSpeech();
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    voiceStatus.textContent = "Firefox does not support mic dictation here. Voice replies still work; type the question or open Chrome/Safari for Ask by voice.";
    rasaMessage.focus();
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.continuous = false;
  recognition.onstart = () => {
    voiceStatus.textContent = "Listening...";
  };
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    rasaMessage.value = transcript;
    voiceStatus.textContent = `Heard: "${transcript}"`;
    sendRasaMessage(transcript);
  };
  recognition.onend = () => {
    if (voiceStatus.textContent === "Listening...") {
      voiceStatus.textContent = "Listening stopped. Try Ask by voice again or type the question.";
    }
  };
  recognition.onerror = (event) => {
    const reason = event.error === "not-allowed"
      ? "Microphone permission was blocked."
      : "Voice input had trouble hearing that.";
    voiceStatus.textContent = `${reason} Text fallback is ready.`;
    rasaMessage.focus();
  };
  try {
    recognition.start();
  } catch {
    voiceStatus.textContent = "Voice input could not start. Text fallback is ready.";
    rasaMessage.focus();
  }
});

async function analyze(options = {}) {
  const { speakResult = false } = options;
  setLoading(true);
  try {
    const payload = Object.fromEntries(new FormData(form).entries());
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(`Analysis failed with HTTP ${response.status}`);
    }
    const analysis = await response.json();
    render(analysis);
    if (speakResult) {
      speakRecommendation(analysis);
    }
  } catch (error) {
    appendMessage("error", `Analysis is unavailable: ${error.message}. Restart the local web server and try again.`);
    voiceStatus.textContent = "Analysis backend is not reachable.";
  } finally {
    setLoading(false);
  }
}

async function sendRasaMessage(quickMessage = null) {
  if (chatBusy) return;
  const message = (quickMessage || rasaMessage.value).trim();
  if (!message) return;
  chatBusy = true;
  const enrichedMessage = enrichForSelectedProperty(message);
  appendMessage("user", message);
  showThinking();
  rasaMessage.value = "";
  setChatBusy(true);
  rasaSend.textContent = "Sending";
  try {
    const response = await fetch("/api/rasa-chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sender: "web-demo",
        message: enrichedMessage,
        context: getAnalysisPayload(),
      }),
    });
    const payload = await response.json();
    hideThinking();
    if (payload.error) {
      appendMessage("error", `${payload.error}\n${payload.detail || ""}`.trim());
      return;
    }
    if (!payload.length) {
      appendMessage("agent", "Rasa returned no messages. It may be waiting for another turn.");
      return;
    }
    payload.forEach((item) => {
      const text = item.text || JSON.stringify(item);
      appendMessage("agent", text);
      speak(text);
    });
  } catch (error) {
    hideThinking();
    appendMessage("error", `Could not reach the local Rasa proxy: ${error.message}`);
  } finally {
    chatBusy = false;
    setChatBusy(false);
    rasaSend.textContent = "Send";
  }
}

async function runPitchMode() {
  if (chatBusy) return;
  const spotlight = await loadSpotlight();
  if (!spotlight) return;
  await selectPropertyByParcel(spotlight.biggest_trap.parcel_id);
  stopSpeaking();
  rasaTranscript.innerHTML = "";
  appendMessage("agent", `Here is the judge-ready story: this agent does not just chat. It decides.`);
  appendMessage(
    "agent",
    `Trap found: ${street(spotlight.biggest_trap.address)} needs ${currency.format(spotlight.biggest_trap.current_bid)} today and still leaves ${money(spotlight.biggest_trap.cash_gap)} after cash-to-close.`
  );
  appendMessage(
    "agent",
    `Best fit: ${street(spotlight.best_fit.address)} scores ${spotlight.best_fit.score}/100 with ${money(spotlight.best_fit.monthly_cash_flow)} monthly cash flow.`
  );
  speak(
    `Judge story: the agent screens the whole auction list, flags the trap, and gives a bid call in seconds. Biggest trap: ${street(spotlight.biggest_trap.address)}. Best fit: ${street(spotlight.best_fit.address)}.`
  );
}

async function applySpotlight(kind) {
  if (chatBusy) return;
  const spotlight = await loadSpotlight();
  if (!spotlight) return;
  const card = spotlight[kind];
  await selectPropertyByParcel(card.parcel_id);
  stopSpeaking();
  rasaTranscript.innerHTML = "";
  const label = kind === "best_fit" ? "Best fit" : "Biggest trap";
  const text = `${label}: ${street(card.address)}. Score ${card.score}/100, cash gap ${money(card.cash_gap)}, projected cash flow ${money(card.monthly_cash_flow)} per month. Main issue: ${card.reason}.`;
  appendMessage("agent", text);
  speak(text);
}

async function loadSpotlight() {
  setDemoControlsBusy(true);
  try {
    const response = await fetch("/api/spotlight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(getAnalysisPayload()),
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    appendMessage("error", `Spotlight is unavailable: ${error.message}.`);
    return null;
  } finally {
    setDemoControlsBusy(false);
  }
}

async function selectPropertyByParcel(parcelId) {
  const option = [...propertySelect.options].find((item) => item.value === parcelId);
  if (!option) return;
  propertySelect.value = parcelId;
  propertySelect.dispatchEvent(new Event("change"));
  await wait(300);
}

function enrichForSelectedProperty(message) {
  const selected = propertySelect.selectedOptions[0];
  const parcel = propertySelect.value;
  const address = selected?.dataset.address || form.elements.address.value;
  const currentBid = form.elements.currentBid.value;
  const availableCash = form.elements.availableCash.value;
  const investmentGoal = form.elements.investmentGoal.value;
  const financingType = form.elements.financingType.value;
  const repairs = form.elements.estimatedRepairs.value;
  const rent = form.elements.marketRent.value;

  return [
    message,
    "",
    "Use these selected dashboard details:",
    parcel ? `Parcel/property id: ${parcel}` : `Property address: ${address}`,
    `Address: ${address}`,
    `Current bid: ${currentBid}`,
    `Available cash: ${availableCash}`,
    `Investment goal: ${investmentGoal}`,
    `Financing type: ${financingType}`,
    repairs ? `Estimated repairs: ${repairs}` : null,
    rent ? `Market rent: ${rent}` : null,
  ].filter(Boolean).join("\n");
}

function appendMessage(kind, text) {
  const bubble = document.createElement("div");
  bubble.className = `message ${kind}`;
  bubble.textContent = text;
  rasaTranscript.appendChild(bubble);
  rasaTranscript.scrollTop = rasaTranscript.scrollHeight;
}

function showThinking() {
  hideThinking();
  currentThinkingBubble = document.createElement("div");
  currentThinkingBubble.className = "message agent thinking";
  currentThinkingBubble.innerHTML = "<span></span><span></span><span></span>";
  rasaTranscript.appendChild(currentThinkingBubble);
  rasaTranscript.scrollTop = rasaTranscript.scrollHeight;
}

function hideThinking() {
  currentThinkingBubble?.remove();
  currentThinkingBubble = null;
}

function speakRecommendation(analysis) {
  const rec = analysis.recommendation;
  const text = [
    `${rec.category}.`,
    `Max safe bid ${currency.format(rec.max_safe_bid)}.`,
    `Main issue: ${rec.biggest_risk}.`,
  ].join(" ");
  speak(text);
}

function hydrateVoiceControls() {
  if (!("speechSynthesis" in window)) {
    voiceStatus.textContent = "Browser voice is unavailable. The local system voice will be tried instead.";
    return;
  }

  const loadVoices = () => {
    const voices = window.speechSynthesis.getVoices();
    selectedVoice =
      voices.find((voice) => voice.lang?.startsWith("en-US") && /Samantha|Google|Microsoft|Natural/i.test(voice.name)) ||
      voices.find((voice) => voice.lang?.startsWith("en")) ||
      voices[0] ||
      null;
  };
  loadVoices();
  window.speechSynthesis.onvoiceschanged = loadVoices;
}

function hydrateVoiceInputControls() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) return;

  voiceButton.classList.add("unsupported");
  voiceButton.setAttribute("aria-disabled", "true");
  voiceButton.querySelector("span:last-child").textContent = "Mic unavailable";
  voiceButton.title = "Firefox does not support browser speech recognition. Typed chat and voice replies still work.";
  voiceStatus.textContent = "Firefox can play voice replies, but mic input needs Chrome or Safari. Type a question below for this browser.";
}

function unlockSpeech() {
  primeAudio();
  if (!("speechSynthesis" in window)) return;
  if (!selectedVoice) {
    selectedVoice = window.speechSynthesis.getVoices()[0] || null;
  }
  if (window.speechSynthesis.paused) {
    window.speechSynthesis.resume();
  }
}

async function speak(text) {
  if (!voiceRepliesEnabled) return;
  const cleanText = text
    .replace(/\s+/g, " ")
    .replace(/\$([0-9,]+)/g, "$1 dollars")
    .slice(0, 420);

  stopSpeaking();
  if (await speakWithSystemVoice(cleanText)) {
    return;
  }

  if (await speakWithGeneratedAudio(cleanText)) {
    return;
  }

  if (!("speechSynthesis" in window)) {
    voiceStatus.textContent = "Voice reply is unavailable in this browser.";
    return;
  }

  speechQueue.push(cleanText);
  voiceStatus.textContent = speechActive ? "Queued voice response..." : "Preparing voice response...";
  playNextSpeech();
}

async function speakWithSystemVoice(text) {
  try {
    voiceStatus.textContent = "Speaking with local system voice...";
    const response = await fetch("/api/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const payload = await response.json();
    if (!payload.ok) {
      voiceStatus.textContent = "Local system voice failed. Trying browser audio...";
      return false;
    }
    return true;
  } catch {
    voiceStatus.textContent = "Local system voice failed. Trying browser audio...";
    return false;
  }
}

async function speakWithGeneratedAudio(text) {
  try {
    voiceStatus.textContent = "Generating voice reply...";
    const response = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!response.ok || !response.headers.get("Content-Type")?.includes("audio/")) {
      return false;
    }
    const blob = await response.blob();
    const audioUrl = URL.createObjectURL(blob);
    replyAudio.pause();
    if (replyAudio.src?.startsWith("blob:")) {
      URL.revokeObjectURL(replyAudio.src);
    }
    replyAudio = new Audio(audioUrl);
    replyAudio.onplay = () => {
      voiceStatus.textContent = "Speaking response...";
    };
    replyAudio.onended = () => {
      voiceStatus.textContent = "Ready for the next question.";
      URL.revokeObjectURL(audioUrl);
    };
    replyAudio.onerror = () => {
      voiceStatus.textContent = "Audio playback failed. Text response is still available.";
      URL.revokeObjectURL(audioUrl);
    };
    await replyAudio.play();
    return true;
  } catch {
    voiceStatus.textContent = "Generated voice was blocked. Trying browser voice...";
    return false;
  }
}

function playNextSpeech() {
  if (speechActive || !speechQueue.length || !("speechSynthesis" in window)) return;
  const cleanText = speechQueue.shift();
  const utterance = new SpeechSynthesisUtterance(cleanText);
  if (selectedVoice) {
    utterance.voice = selectedVoice;
  }
  utterance.rate = 0.96;
  utterance.pitch = 1;
  utterance.onstart = () => {
    voiceStatus.textContent = "Speaking response...";
  };
  utterance.onend = () => {
    speechActive = false;
    voiceStatus.textContent = speechQueue.length
      ? "Speaking next response..."
      : "Ready for the next question.";
    playNextSpeech();
  };
  utterance.onerror = () => {
    speechActive = false;
    voiceStatus.textContent = "Voice reply had trouble. The text response is still available.";
    playNextSpeech();
  };
  speechActive = true;
  window.speechSynthesis.speak(utterance);
  window.setTimeout(() => {
    if (speechActive && !window.speechSynthesis.speaking) {
      speechActive = false;
      voiceStatus.textContent = "Browser voice stayed silent. Try Test voice or use Safari/Chrome with sound enabled.";
      playNextSpeech();
    }
  }, 1200);
}

function stopSpeaking() {
  replyAudio.pause();
  if (replyAudio.src?.startsWith("blob:")) {
    URL.revokeObjectURL(replyAudio.src);
  }
  replyAudio = new Audio();
  window.speechSynthesis?.cancel();
  speechQueue = [];
  speechActive = false;
  fetch("/api/stop-speech", { method: "POST" }).catch(() => {});
}

function setChatBusy(isBusy) {
  rasaSend.disabled = isBusy;
  askDecision.disabled = isBusy;
  askRisks.disabled = isBusy;
  askMaxBid.disabled = isBusy;
}

function setDemoControlsBusy(isBusy) {
  pitchMode.disabled = isBusy;
  bestFit.disabled = isBusy;
  biggestTrap.disabled = isBusy;
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function street(address) {
  return String(address || "").split(",")[0];
}

function money(value) {
  const amount = Number(value || 0);
  const formatted = currency.format(Math.abs(amount));
  return amount < 0 ? `-${formatted}` : formatted;
}

function primeAudio() {
  if (primedAudio) return;
  primedAudio = true;
  const silentAudio =
    "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=";
  const audio = new Audio(silentAudio);
  audio.volume = 0;
  audio.play().catch(() => {
    primedAudio = false;
  });
}

function getAnalysisPayload() {
  return Object.fromEntries(new FormData(form).entries());
}

async function loadProperties() {
  const response = await fetch("/api/properties");
  const payload = await response.json();
  const defaultOption = propertySelect.options[0];
  defaultOption.dataset.address = "6013 Fender Court";
  defaultOption.dataset.currentBid = "170000";
  defaultOption.dataset.minimumBid = "170000";
  defaultOption.dataset.deposit = "25000";
  payload.properties.forEach((property) => {
    const option = document.createElement("option");
    option.value = property.parcel_id;
    option.textContent = `${property.parcel_id} · ${property.address}`;
    option.dataset.address = property.address;
    option.dataset.currentBid = property.current_bid || "";
    option.dataset.minimumBid = property.minimum_bid || "";
    option.dataset.auctionDate = property.auction_date || "";
    option.dataset.deposit = property.deposit_required || "";
    propertySelect.appendChild(option);
  });
  renderPropertySummary(normalizeSelectedDeal(propertySelect.selectedOptions[0]));
}

function normalizeSelectedDeal(selected) {
  return {
    address: selected?.dataset.address || "6013 Fender Court",
    currentBid: selected?.dataset.currentBid || selected?.dataset.minimumBid || form.elements.currentBid.value || "170000",
    deposit: selected?.dataset.deposit || "25000",
    auctionDate: selected?.dataset.auctionDate || "",
  };
}

function renderPropertySummary(deal) {
  const address = deal.address;
  const bid = deal.currentBid;
  const deposit = deal.deposit;
  const auctionDate = deal.auctionDate;
  propertySummary.innerHTML = `
    <span>Selected deal</span>
    <strong>${address}</strong>
    <small>${[
      bid ? `Bid ${currency.format(Number(bid))}` : null,
      deposit ? `Deposit ${currency.format(Number(deposit))}` : null,
      auctionDate ? `Auction ${auctionDate}` : null,
    ].filter(Boolean).join(" · ") || "Official auction facts and diligence assumptions loaded."}</small>
  `;
}

function resetChatForSelection(deal) {
  stopSpeaking();
  rasaTranscript.innerHTML = "";
  appendMessage("agent", `Loaded ${deal.address.split(",")[0]}. Ask whether to bid, what could go wrong, or the max bid.`);
  voiceStatus.textContent = "Deal loaded. Voice replies are ready.";
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
  button.textContent = isLoading ? "Analyzing..." : "Analyze selected property";
}

analyze();
loadSources();
loadProperties();
