const GA_MEASUREMENT_ID = "G-1C612TT8W0"; // GA4 측정 ID. 비우면 추적 없이 동작.

const ICONS = {
  instagram:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.2" cy="6.8" r=".9" fill="currentColor" stroke="none"/></svg>',
  youtube:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="2.5" y="5.5" width="19" height="13" rx="3.5"/><path d="M10 9.5v5l4.5-2.5z" fill="currentColor" stroke="none"/></svg>',
  link:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M9 15l6-6"/><path d="M11 6.5l1.5-1.5a4 4 0 015.5 5.5L16.5 12"/><path d="M13 17.5L11.5 19a4 4 0 01-5.5-5.5L7.5 12"/></svg>',
};

function setupAnalytics() {
  if (!GA_MEASUREMENT_ID) return;
  const s = document.createElement("script");
  s.async = true;
  s.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_MEASUREMENT_ID;
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };
  gtag("js", new Date());
  gtag("config", GA_MEASUREMENT_ID);
}

function trackClick(product) {
  if (!GA_MEASUREMENT_ID || typeof window.gtag !== "function") return;
  gtag("event", "select_item", {
    item_list_id: "todaysingi_link_hub",
    item_list_name: "오늘의신기템 링크 허브",
    items: [{
      item_id: String(product.id).padStart(3, "0"),
      item_name: product.title,
    }],
  });
}

const displayName = (p) => "[" + String(p.id).padStart(3, "0") + "] " + p.title;
const displayPrice = (p) => p.price.toLocaleString("ko-KR") + "원";

function renderProfile(profile) {
  const root = document.getElementById("profile");

  if (profile.avatar) {
    const img = document.createElement("img");
    img.className = "avatar";
    img.src = profile.avatar;
    img.alt = profile.name;
    img.onerror = () => img.replaceWith(makeAvatarFallback(profile.name));
    root.appendChild(img);
  } else {
    root.appendChild(makeAvatarFallback(profile.name));
  }

  const h1 = document.createElement("h1");
  h1.textContent = profile.name;
  root.appendChild(h1);

  const bio = document.createElement("p");
  bio.className = "bio";
  bio.textContent = profile.bio;
  root.appendChild(bio);

  const links = (profile.links || []).filter((l) => l.url);
  if (links.length) {
    const nav = document.createElement("nav");
    nav.className = "sns";
    for (const l of links) {
      const a = document.createElement("a");
      a.href = l.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.setAttribute("aria-label", l.type);
      a.innerHTML = ICONS[l.type] || ICONS.link;
      nav.appendChild(a);
    }
    root.appendChild(nav);
  }
}

function makeAvatarFallback(name) {
  const div = document.createElement("div");
  div.className = "avatar-fallback";
  div.textContent = (name || "?").slice(0, 1);
  return div;
}

function renderProducts(products) {
  const root = document.getElementById("products");
  root.replaceChildren();
  for (const p of products) {
    const card = document.createElement("article");
    card.className = "card";

    const img = document.createElement("img");
    img.className = "thumb";
    img.src = p.image;
    img.alt = p.title;
    img.loading = "lazy";
    img.onerror = () => { img.removeAttribute("src"); img.alt = ""; };
    card.appendChild(img);

    const body = document.createElement("div");
    body.className = "card-body";

    const h2 = document.createElement("h2");
    h2.textContent = displayName(p);
    body.appendChild(h2);

    const price = document.createElement("p");
    price.className = "price";
    price.textContent = displayPrice(p);
    body.appendChild(price);

    const buy = document.createElement("a");
    buy.className = "buy";
    buy.href = p.link;
    buy.target = "_blank";
    buy.rel = "noopener sponsored";
    buy.textContent = "구매하기";
    buy.addEventListener("click", () => trackClick(p));
    body.appendChild(buy);

    card.appendChild(body);
    root.appendChild(card);
  }
}

function showStatus(message) {
  const status = document.getElementById("status");
  status.textContent = message;
  status.hidden = false;
}

function hideStatus() {
  document.getElementById("status").hidden = true;
}

const SEARCH_MIN_ITEMS = 5; // 활성 상품이 이 수 이상일 때만 검색창 노출

function setupSearch(items) {
  if (items.length < SEARCH_MIN_ITEMS) return;
  const box = document.getElementById("search-box");
  const input = document.getElementById("search");
  box.hidden = false;
  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    const filtered = q
      ? items.filter((p) => displayName(p).toLowerCase().includes(q))
      : items;
    renderProducts(filtered);
    if (filtered.length === 0) {
      showStatus("검색 결과가 없어요.");
    } else {
      hideStatus();
    }
  });
}

async function init() {
  setupAnalytics();
  try {
    const res = await fetch("products.json", { cache: "no-cache" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    renderProfile(data.profile);
    const items = data.products
      .filter((p) => p.active)
      .sort((a, b) => b.id - a.id);
    if (items.length === 0) {
      showStatus("곧 신기한 물건들이 올라올 거예요.");
      return;
    }
    renderProducts(items);
    setupSearch(items);
  } catch (e) {
    showStatus("상품을 불러오지 못했어요. 잠시 후 새로고침해 주세요.");
  }
}

init();
