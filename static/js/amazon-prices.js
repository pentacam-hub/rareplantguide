(() => {
  const priceNodes = Array.from(document.querySelectorAll('[data-amazon-price]'));
  if (!priceNodes.length) return;

  // Do not hard-code old Amazon prices. Until the live price endpoint is configured,
  // the page keeps the neutral "Check current price" state and sends shoppers to Amazon.
  const fallbackPrices = {};

  const formatUpdated = (iso) => {
    if (!iso) return 'Live Amazon price';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return 'Live Amazon price';
    return `Amazon price • updated ${date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`;
  };

  const applyFallback = () => {
    priceNodes.forEach((node) => {
      const asin = node.getAttribute('data-amazon-price');
      const item = fallbackPrices[asin];
      if (!item) return;

      const label = node.querySelector('.amazon-price-label');
      const value = node.querySelector('.amazon-price-value');
      const updated = node.querySelector('.amazon-price-updated');

      node.classList.add('is-fallback');
      if (label) label.textContent = 'Recent tracked price';
      if (value) value.textContent = item.displayAmount;
      if (updated) updated.textContent = 'Price snapshot • verify current price on Amazon';
    });
  };

  applyFallback();

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

        const label = node.querySelector('.amazon-price-label');
        const value = node.querySelector('.amazon-price-value');
        const updated = node.querySelector('.amazon-price-updated');

        node.classList.remove('is-fallback');

        if (item.mapRestricted) {
          node.classList.add('is-map');
          if (label) label.textContent = 'Amazon price';
          if (value) value.textContent = 'See price on Amazon';
          if (updated) updated.textContent = 'Price must be revealed on Amazon';
          return;
        }

        if (item.displayAmount) {
          node.classList.add('is-live');
          if (label) label.textContent = 'Current Amazon price';
          if (value) value.textContent = item.displayAmount;
          if (updated) updated.textContent = formatUpdated(item.updatedAt || payload.updatedAt);
        }
      });
    })
    .catch(() => {
      // Keep the neutral "Check current price" state when live pricing is unavailable.
    });
})();