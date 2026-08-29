(() => {
  const priceNodes = Array.from(document.querySelectorAll('[data-amazon-price]'));
  if (!priceNodes.length) return;

  const fallbackPrices = {
    B0F5GTD4HN: { displayAmount: '$42.99', checked: 'Aug 29, 2026' },
    B0DGXF9B8S: { displayAmount: '$35.98', checked: 'Aug 29, 2026' },
    B0CL4WHFVS: { displayAmount: '$137.99', checked: 'Aug 29, 2026' },
    B091DLFDL9: { displayAmount: '$8.99', checked: 'Aug 29, 2026' },
    B085CDPSMR: { displayAmount: '$21.45', checked: 'Aug 29, 2026' },
    B0C36WZBWC: { displayAmount: '$25.99', checked: 'Aug 29, 2026' }
  };

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
      if (updated) updated.textContent = `Checked ${item.checked} • verify current price on Amazon`;
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
      // Keep the verified dated fallback until Amazon Creators API credentials are enabled.
    });
})();