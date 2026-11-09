const state = { category: 'all', priority: 'all', q: '', sort: 'newest', page: 0, pageSize: 30, total: 0, loading: false };
const $ = (id) => document.getElementById(id);
let searchTimer;
let toastTimer;

function escapeText(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

function categoryName(category) {
  return ({formula1:'Formula 1',ufc:'UFC',football:'Football'})[category] || 'Sports';
}

function formatDate(value) {
  if (!value) return 'Date not provided';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Date not provided';
  return new Intl.DateTimeFormat(undefined, {dateStyle:'medium', timeStyle:'short'}).format(date);
}

function showToast(message) {
  $('toast').textContent = message;
  $('toast').classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.remove('show'), 3200);
}

function updateCategory(category) {
  state.category = category;
  state.page = 0;
  document.querySelectorAll('[data-category]').forEach((button) => {
    const active = button.dataset.category === category;
    button.classList.toggle('active', active && button.classList.contains('tab'));
    button.classList.toggle('selected', active && button.classList.contains('category-link'));
  });
  loadArticles();
}

async function loadStats() {
  const response = await fetch('/api/stats');
  if (!response.ok) throw new Error('Could not load newsroom statistics.');
  const stats = await response.json();
  $('stat-total').textContent = stats.total.toLocaleString();
  $('stat-f1').textContent = (stats.categories.formula1 || 0).toLocaleString();
  $('stat-ufc').textContent = (stats.categories.ufc || 0).toLocaleString();
  $('stat-football').textContent = (stats.categories.football || 0).toLocaleString();
  $('side-all').textContent = stats.total;
  $('side-f1').textContent = stats.categories.formula1 || 0;
  $('side-ufc').textContent = stats.categories.ufc || 0;
  $('side-football').textContent = stats.categories.football || 0;
  $('source-count').textContent = stats.sources;
  $('today-label').textContent = new Intl.DateTimeFormat(undefined, {weekday:'short', month:'short', day:'numeric'}).format(new Date());
  $('last-checked').textContent = stats.last_scan
    ? `Last checked: ${formatDate(stats.last_scan)} · ${stats.last_scan_new} new`
    : 'Last checked: not yet';
}

function renderArticles(articles) {
  const list = $('article-list');
  if (!articles.length) {
    list.innerHTML = '<div class="empty-state"><strong>No stories found</strong>Try changing your category, search term, or priority filter.</div>';
    return;
  }
  list.innerHTML = articles.map((article) => {
    const category = escapeText(article.category);
    const priority = escapeText(article.priority.toLowerCase());
    const title = escapeText(article.title);
    const summary = escapeText(article.summary || 'No summary was provided by this feed.');
    const source = escapeText(article.source);
    const url = escapeText(article.url);
    return `<article class="article-card">
      <div class="article-top"><span class="category-pill ${category}">${escapeText(categoryName(article.category))}</span><span class="priority-pill ${priority}">${escapeText(article.priority)} PRIORITY</span><time class="article-time">${escapeText(formatDate(article.published || article.first_seen))}</time></div>
      <a class="article-title" href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>
      <p class="article-summary">${summary}</p>
      <div class="article-bottom"><span class="article-source">Source: <strong>${source}</strong></span><a class="open-link" href="${url}" target="_blank" rel="noopener noreferrer">Read original ↗</a></div>
    </article>`;
  }).join('');
}

async function loadArticles() {
  if (state.loading) return;
  state.loading = true;
  $('article-list').innerHTML = '<div class="loading-state"><span class="spinner"></span>Loading stories…</div>';
  const params = new URLSearchParams({category:state.category, priority:state.priority, q:state.q, sort:state.sort, limit:state.pageSize, offset:state.page*state.pageSize});
  try {
    const response = await fetch(`/api/articles?${params}`);
    if (!response.ok) throw new Error('Could not load articles.');
    const data = await response.json();
    state.total = data.total;
    renderArticles(data.articles);
    const start = data.total ? state.page * state.pageSize + 1 : 0;
    const end = Math.min((state.page + 1) * state.pageSize, data.total);
    $('feed-count').textContent = `${data.total.toLocaleString()} ${data.total === 1 ? 'story' : 'stories'} found`;
    $('result-caption').textContent = state.category === 'all' ? 'Browse all collected articles' : `Browsing ${categoryName(state.category)} stories`;
    $('pagination-info').textContent = data.total ? `Showing ${start}–${end} of ${data.total.toLocaleString()}` : '';
    $('prev-page').disabled = state.page === 0;
    $('next-page').disabled = end >= data.total;
  } catch (error) {
    $('article-list').innerHTML = `<div class="empty-state"><strong>Unable to load stories</strong>${escapeText(error.message)}</div>`;
  } finally {
    state.loading = false;
  }
}

async function refreshNews() {
  if (state.loading) return;
  const button = $('refresh-button');
  button.disabled = true;
  $('refresh-label').textContent = 'Collecting…';
  try {
    const response = await fetch('/api/refresh', {method:'POST'});
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.message || 'Refresh failed.');
    await loadStats();
    state.page = 0;
    await loadArticles();
    const errors = result.errors.length;
    showToast(`${result.new_articles} new stories collected${errors ? ` · ${errors} source errors` : ' · all sources checked'}`);
  } catch (error) {
    showToast(error.message);
  } finally {
    button.disabled = false;
    $('refresh-label').textContent = 'Refresh news';
  }
}

document.querySelectorAll('[data-category]').forEach((button) => button.addEventListener('click', () => updateCategory(button.dataset.category)));
$('priority-select').addEventListener('change', (event) => { state.priority = event.target.value; state.page = 0; loadArticles(); });
$('sort-select').addEventListener('change', (event) => { state.sort = event.target.value; state.page = 0; loadArticles(); });
$('search-input').addEventListener('input', (event) => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { state.q = event.target.value; state.page = 0; loadArticles(); }, 250); });
$('clear-filters').addEventListener('click', () => { state.priority = 'all'; state.q = ''; state.sort = 'newest'; state.page = 0; $('priority-select').value = 'all'; $('search-input').value = ''; $('sort-select').value = 'newest'; updateCategory('all'); });
$('refresh-button').addEventListener('click', refreshNews);
$('prev-page').addEventListener('click', () => { if (state.page > 0) { state.page--; loadArticles(); } });
$('next-page').addEventListener('click', () => { if ((state.page + 1) * state.pageSize < state.total) { state.page++; loadArticles(); } });

async function syncDashboard() {
  try {
    await loadStats();
    await loadArticles();
  } catch (error) {
    showToast(error.message);
  }
}

Promise.all([loadStats(), loadArticles()]).catch((error) => showToast(error.message));
// Scheduled collector runs independently; refresh the visible dashboard periodically.
setInterval(syncDashboard, 120000);
