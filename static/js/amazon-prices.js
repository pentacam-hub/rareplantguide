(() => {
  const priceNodes = Array.from(document.querySelectorAll('[data-amazon-price]'));
  if (!priceNodes.length) return;

  const formatUpdated = (iso) => {
    if (!iso) return 'Live Amazon price';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return 'Live Amazon price';
    return `Amazon price • updated ${date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`;
  };

  fetch('/api/amazon-prices', {
    method: 'GET',
    headers: { Accept: 'application/json' },
    credentials: 'same-origin'
  })
    .then((response) => {
      if (!response.ok) throw new Error(`Amazon price API ${response.status}`);
      return response.json();
    })
    .then((payload) => {
      const prices = payload && payload.prices ? payload.prices : {};
      priceNodes.forEach((node) => {
        const asin = node.getAttribute('data-amazon-price');
        const item = prices[asin];
        if (!item) return;

        const value = node.querySelector('.amazon-price-value');
        const updated = node.querySelector('.amazon-price-updated');

        if (item.mapRestricted) {
          node.classList.add('is-map');
          if (value) value.textContent = 'See price on Amazon';
          if (updated) updated.textContent = 'Price must be revealed on Amazon';
          return;
        }

        if (item.displayAmount) {
          node.classList.add('is-live');
          if (value) value.textContent = item.displayAmount;
          if (updated) updated.textContent = formatUpdated(item.updatedAt || payload.updatedAt);
        }
      });
    })
    .catch(() => {
      // Keep the server-rendered fallback. Buying guides remain fully usable
      // before Amazon Creators API credentials are enabled.
    });
})();