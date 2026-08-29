const $ = (selector) => document.querySelector(selector);
const formatter = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const pct = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 2 });

function numberOrDash(value, render = formatter.format.bind(formatter)) {
  return value === null || value === undefined ? "—" : render(value);
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function scoreCell(value) {
  const td = element("td");
  td.append(element("span", formatter.format(value), "score"));
  return td;
}

function setApiState(text, ok = true) {
  const node = $("#apiState");
  node.textContent = text;
  node.dataset.state = ok ? "ok" : "error";
}

async function api(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function rankingParams() {
  const params = new URLSearchParams();
  const sector = $("#sector").value.trim();
  const status = $("#status").value;
  const minScore = $("#minScore").value;
  if (sector) params.set("sector", sector);
  if (status) params.set("status", status);
  if (minScore) params.set("min_investment_score", minScore);
  params.set("rankable_only", $("#rankableOnly").checked ? "true" : "false");
  params.set("limit", "200");
  return params;
}

function renderRanking(payload) {
  const body = $("#rankingBody");
  body.replaceChildren();
  $("#emptyState").hidden = payload.items.length !== 0;
  $("#assetCount").textContent = String(payload.total);
  $("#asOf").textContent = payload.as_of ?? "—";
  $("#topScore").textContent = payload.items.length ? formatter.format(payload.items[0].investment_attractiveness) : "—";
  const confidence = payload.items.map((row) => row.data_confidence);
  $("#topConfidence").textContent = confidence.length ? formatter.format(Math.max(...confidence)) : "—";

  for (const row of payload.items) {
    const tr = document.createElement("tr");
    tr.tabIndex = 0;
    tr.setAttribute("role", "button");
    tr.setAttribute("aria-label", `Abrir análise de ${row.ticker}`);
    tr.append(element("td", String(row.rank)));
    const identity = element("td");
    identity.append(element("span", row.ticker, "ticker"));
    identity.append(element("span", row.company_name, "company"));
    tr.append(identity);
    tr.append(element("td", numberOrDash(row.current_price, money.format.bind(money))));
    tr.append(element("td", numberOrDash(row.dy_ttm, pct.format.bind(pct))));
    tr.append(scoreCell(row.company_quality));
    tr.append(scoreCell(row.investment_attractiveness));
    tr.append(scoreCell(row.entry_timing));
    tr.append(scoreCell(row.data_confidence));
    tr.append(element("td", numberOrDash(row.lending_rate_annual, pct.format.bind(pct))));
    const status = element("td");
    status.append(element("span", row.status, "pill"));
    tr.append(status);
    const open = () => openDetail(row.ticker);
    tr.addEventListener("click", open);
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
    body.append(tr);
  }
}

function scoreCard(label, value) {
  const card = element("article", null, "score-card");
  card.append(element("span", label));
  card.append(element("strong", formatter.format(value)));
  return card;
}

async function openDetail(ticker) {
  try {
    const row = await api(`/v1/stocks/${encodeURIComponent(ticker)}`);
    $("#detailTicker").textContent = `${row.ticker} · ${row.sector}`;
    $("#detailTitle").textContent = row.company_name;
    const content = $("#detailContent");
    content.replaceChildren();

    const scores = element("div", null, "score-grid");
    scores.append(scoreCard("Qualidade da empresa", row.scores.company_quality));
    scores.append(scoreCard("Atratividade", row.scores.investment_attractiveness));
    scores.append(scoreCard("Momento de entrada", row.scores.entry_timing));
    scores.append(scoreCard("Confiança dos dados", row.scores.data_confidence));
    scores.append(scoreCard("Ranking", row.scores.ranking_score));
    scores.append(scoreCard("Actionability", row.scores.actionability_score));
    content.append(scores);

    content.append(element("h3", "Componentes"));
    const components = element("ul", null, "component-list");
    for (const [name, value] of Object.entries(row.scores.components).sort()) {
      const item = element("li");
      item.append(element("span", name));
      item.append(element("strong", formatter.format(value)));
      components.append(item);
    }
    if (!Object.keys(row.scores.components).length) components.append(element("li", "Sem componentes publicados."));
    content.append(components);

    content.append(element("h3", "Evidências"));
    const evidence = element("ul", null, "evidence-list");
    for (const source of row.evidence) {
      const item = element("li");
      const label = source.source_document ? `${source.source} — ${source.source_document}` : source.source;
      if (source.url) {
        const link = element("a", label);
        link.href = source.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        item.append(link);
      } else {
        item.textContent = label;
      }
      evidence.append(item);
    }
    if (!row.evidence.length) evidence.append(element("li", "Nenhuma referência publicada nesta análise."));
    content.append(evidence);
    $("#detailDialog").showModal();
  } catch (error) {
    setApiState(`Falha ao carregar ${ticker}: ${error.message}`, false);
  }
}

function renderBacktests(rows) {
  const root = $("#backtests");
  root.replaceChildren();
  if (!rows.length) {
    root.append(element("p", "Nenhum backtest publicado."));
    return;
  }
  for (const row of rows) {
    const card = element("article", null, "backtest-card");
    card.append(element("h3", row.backtest_id));
    const values = element("div", null, "backtest-values");
    const entries = [
      ["CAGR", pct.format(row.cagr)],
      ["Benchmark", pct.format(row.benchmark_cagr)],
      ["Drawdown máx.", pct.format(row.max_drawdown)],
      ["Sharpe", numberOrDash(row.sharpe)],
    ];
    for (const [label, value] of entries) {
      const item = element("div");
      item.append(element("span", label));
      item.append(element("strong", value));
      values.append(item);
    }
    card.append(values);
    root.append(card);
  }
}

async function loadRanking() {
  try {
    const payload = await api(`/v1/ranking?${rankingParams()}`);
    renderRanking(payload);
    setApiState("API conectada");
  } catch (error) {
    setApiState(`API indisponível: ${error.message}`, false);
  }
}

async function init() {
  $("#filterForm").addEventListener("submit", (event) => {
    event.preventDefault();
    loadRanking();
  });
  $("#resetFilters").addEventListener("click", () => {
    $("#filterForm").reset();
    $("#rankableOnly").checked = true;
    loadRanking();
  });
  $("#closeDialog").addEventListener("click", () => $("#detailDialog").close());
  await Promise.all([
    loadRanking(),
    api("/v1/backtests").then(renderBacktests).catch(() => renderBacktests([])),
  ]);
}

init();
