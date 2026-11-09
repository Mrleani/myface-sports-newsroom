const state = {
  category: 'all',
  priority: 'all',
  q: '',
  sort: 'newest',
  page: 0,
  pageSize: 30,
  total: 0,
  articles: [],
  loading: false
};

const $ = (id) => document.getElementById(id);
let searchTimer;

function escapeText(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&':'&amp;',
    '<':'&lt;',
    '>':'&gt;',
    '"':'&quot;',
    "'":'&#39;'
  }[char]));
}

function categoryName(category) {
  return ({
    formula1:'Formula 1',
    ufc:'UFC',
    football:'Football'
  })[category] || 'Sports';
}

function formatDate(value) {
  if (!value) return 'Date not provided';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Date not provided';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle:'medium',
    timeStyle:'short'
  }).format(date);
}

function showToast(message) {
  $('toast').textContent = message;
  $('toast').classList.add('show');
  setTimeout(() => $('toast').classList.remove('show'), 3000);
}

function updateCategory(category) {
  state.category = category;
  state.page = 0;

  document.querySelectorAll('[data-category]').forEach((button) => {
    const active = button.dataset.category === category;
    button.classList.toggle('active', active && button.classList.contains('tab'));
    button.classList.toggle('selected', active && button.classList.contains('category-link'));
  });

  renderArticles();
}

function loadStats(stats) {
  $('stat-total').textContent = stats.total.toLocaleString();
  $('stat-f1').textContent = (stats.categories.formula1 || 0).toLocaleString();
  $('stat-ufc').textContent = (stats.categories.ufc || 0).toLocaleString();
  $('stat-football').textContent = (stats.categories.football || 0).toLocaleString();

  $('side-all').textContent = stats.total;
  $('side-f1').textContent = stats.categories.formula1 || 0;
  $('side-ufc').textContent = stats.categories.ufc || 0;
  $('side-football').textContent = stats.categories.football || 0;
  $('source-count').textContent = stats.sources;

  $('today-label').textContent = new Intl.DateTimeFormat(undefined, {
    weekday:'short',
    month:'short',
    day:'numeric'
  }).format(new Date());

  $('last-checked').textContent = stats.last_scan
    ? `Last checked: ${formatDate(stats.last_scan)} · ${stats.last_scan_new} new`
    : 'Last checked: not yet';
}

function renderArticles() {
  const query = state.q.trim().toLowerCase();

  let filtered = state.articles.filter((article) => {
    const categoryMatch = state.category === 'all' || article.category === state.category;
    const priorityMatch = state.priority === 'all' || article.priority === state.priority;
    const searchMatch = !query || [
      article.title,
      article.summary,
      article.source
    ].some((value) => String(value || '').toLowerCase().includes(query));

    return categoryMatch && priorityMatch && searchMatch;
  });

  filtered.sort((a, b) => {
    const dateA = new Date(a.published || a.first_seen || 0).getTime() || 0;
    const dateB = new Date(b.published || b.first_seen || 0).getTime() || 0;
    return state.sort === 'newest' ? dateB - dateA : dateA - dateB;
  });

  state.total = filtered.length;

  const startIndex = state.page * state.pageSize;
  const pageArticles = filtered.slice(startIndex, startIndex + state.pageSize);

  const list = $('article-list');

  if (!pageArticles.length) {
    list.innerHTML = '<div class="empty-state"><strong>No stories found</strong>Try changing your category, search term, or priority filter.</div>';
  } else {
    list.innerHTML = pageArticles.map((article) => {
      const category = escapeText(article.category);
      const priority = escapeText(String(article.priority || 'LOW').toLowerCase());
      const title = escapeText(article.title);
      const summary = escapeText(article.summary || 'No summary was provided by this feed.');
      const source = escapeText(article.source);
      const url = escapeText(article.url);

      return `<article class="article-card">
        <div class="article-top">
          <span class="category-pill ${category}">${escapeText(categoryName(article.category))}</span>
          <span class="priority-pill ${priority}">${escapeText(article.priority)} PRIORITY</span>
          <time class="article-time">${escapeText(formatDate(article.published || article.first_seen))}</time>
        </div>
        <a class="article-title" href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>
        <p class="article-summary">${summary}</p>
        <div class="article-bottom">
          <span class="article-source">Source: <strong>${source}</strong></span>
          <a class="open-link" href="${url}" target="_blank" rel="noopener noreferrer">Read original ↗</a>
        </div>
      </article>`;
    }).join('');
  }

  const end = Math.min(startIndex + state.pageSize, filtered.length);

  $('feed-count').textContent = `${filtered.length.toLocaleString()} ${filtered.length === 1 ? 'story' : 'stories'} found`;
  $('result-caption').textContent = state.category === 'all'
    ? 'Browse all collected articles'
    : `Browsing ${categoryName(state.category)} stories`;

  $('pagination-info').textContent = filtered.length
    ? `Showing ${startIndex + 1}–${end} of ${filtered.length.toLocaleString()}`
    : '';

  $('prev-page').disabled = state.page === 0;
  $('next-page').disabled = end >= filtered.length;
}

async function loadDashboard(showMessage = false) {
  if (state.loading) return;

  state.loading = true;
  const button = $('refresh-button');
  button.disabled = true;
  $('refresh-label').textContent = 'Checking…';

  try {
    const response = await fetch(`data.json?v=${Date.now()}`, {
      cache: 'no-store'
    });

    if (!response.ok) throw new Error('Could not load newsroom data.');

    const data = await response.json();

    state.articles = data.articles || [];
    loadStats(data.stats);
    renderArticles();

    if (showMessage) showToast('Dashboard data checked successfully.');
  } catch (error) {
    $('article-list').innerHTML =
      `<div class="empty-state"><strong>Unable to load stories</strong>${escapeText(error.message)}</div>`;
  } finally {
    state.loading = false;
    button.disabled = false;
    $('refresh-label').textContent = 'Check for updates';
  }
}

document.querySelectorAll('[data-category]').forEach((button) => {
  button.addEventListener('click', () => updateCategory(button.dataset.category));
});

$('priority-select').addEventListener('change', (event) => {
  state.priority = event.target.value;
  state.page = 0;
  renderArticles();
});

$('sort-select').addEventListener('change', (event) => {
  state.sort = event.target.value;
  state.page = 0;
  renderArticles();
});

$('search-input').addEventListener('input', (event) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.q = event.target.value;
    state.page = 0;
    renderArticles();
  }, 250);
});

$('clear-filters').addEventListener('click', () => {
  state.priority = 'all';
  state.q = '';
  state.sort = 'newest';
  state.page = 0;

  $('priority-select').value = 'all';
  $('search-input').value = '';
  $('sort-select').value = 'newest';

  updateCategory('all');
});

$('refresh-button').addEventListener('click', () => loadDashboard(true));

$('prev-page').addEventListener('click', () => {
  if (state.page > 0) {
    state.page--;
    renderArticles();
  }
});

$('next-page').addEventListener('click', () => {
  if ((state.page + 1) * state.pageSize < state.total) {
    state.page++;
    renderArticles();
  }
});

loadDashboard();
setInterval(() => loadDashboard(), 300000);
