// Live tail — open EventSource on the dashboard, prepend new notifications.
// Reconnects with backoff on disconnect. Marked as ".new" for CSS flash.

(function () {
  const feed = document.getElementById('feed');
  if (!feed) return;

  let es = null;
  function connect() {
    es = new EventSource('/api/events/sse');
    es.addEventListener('ready', () => { /* connected */ });
    es.addEventListener('notification', (ev) => {
      try {
        const n = JSON.parse(ev.data);
        const el = renderEvent(n);
        el.classList.add('new');
        feed.prepend(el);
        // Cap at 100 visible entries to avoid runaway DOM growth.
        while (feed.children.length > 100) feed.lastElementChild.remove();
      } catch (err) {
        console.error('sse parse', err);
      }
    });
    es.addEventListener('error', () => {
      // EventSource auto-reconnects, but if it was closed by the server we
      // manually back off.
      if (es && es.readyState === EventSource.CLOSED) {
        es.close();
        setTimeout(connect, 3000);
      }
    });
  }
  function renderEvent(n) {
    const article = document.createElement('article');
    article.className = 'event';
    article.dataset.id = n.notification_id;
    const header = document.createElement('header');
    const name = document.createElement('span');
    name.className = 'event-name'; name.textContent = n.event;
    header.appendChild(name);
    const ts = document.createElement('span');
    ts.className = 'ts';
    ts.textContent = new Date(n.delivered_at).toLocaleString();
    header.appendChild(ts);
    article.appendChild(header);
    if (n.summary) {
      const p = document.createElement('p'); p.textContent = n.summary;
      article.appendChild(p);
    }
    return article;
  }
  connect();
})();