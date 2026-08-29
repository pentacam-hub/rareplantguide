const PRODUCT_ASINS = [
  'B091DLFDL9',
  'B085CDPSMR',
  'B0C36WZBWC',
  'B0F5GTD4HN',
  'B0DGXF9B8S',
  'B0CL4WHFVS'
];

let tokenCache = { value: null, expiresAt: 0 };

function jsonResponse(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'x-content-type-options': 'nosniff',
      ...extraHeaders
    }
  });
}

async function getAccessToken(env) {
  const now = Date.now();
  if (tokenCache.value && tokenCache.expiresAt > now + 60_000) {
    return tokenCache.value;
  }

  const tokenUrl = env.AMAZON_CREATORS_TOKEN_URL || 'https://api.amazon.com/auth/o2/token';
  const response = await fetch(tokenUrl, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      grant_type: 'client_credentials',
      client_id: env.AMAZON_CREATORS_CLIENT_ID,
      client_secret: env.AMAZON_CREATORS_CLIENT_SECRET,
      scope: 'creatorsapi::default'
    })
  });

  if (!response.ok) {
    throw new Error(`Amazon token request failed: ${response.status}`);
  }

  const payload = await response.json();
  if (!payload.access_token) throw new Error('Amazon token response did not contain access_token');

  const expiresIn = Number(payload.expires_in || 3600);
  tokenCache = {
    value: payload.access_token,
    expiresAt: now + Math.max(300, expiresIn - 60) * 1000
  };
  return tokenCache.value;
}

function normalizeItem(item, updatedAt) {
  const listings = item?.offersV2?.listings || [];
  const listing = listings.find((entry) => entry?.isBuyBoxWinner) || listings[0];
  const money = listing?.price?.money;
  const mapRestricted = Boolean(listing?.violatesMAP);

  return {
    asin: item?.asin || null,
    displayAmount: !mapRestricted ? (money?.displayAmount || null) : null,
    amount: !mapRestricted && typeof money?.amount === 'number' ? money.amount : null,
    currency: !mapRestricted ? (money?.currency || null) : null,
    availability: listing?.availability?.type || null,
    mapRestricted,
    detailPageURL: item?.detailPageURL || null,
    updatedAt
  };
}

export async function onRequestGet(context) {
  const { env, request } = context;
  const required = [
    env.AMAZON_CREATORS_CLIENT_ID,
    env.AMAZON_CREATORS_CLIENT_SECRET,
    env.AMAZON_ASSOCIATE_TAG
  ];

  if (required.some((value) => !value)) {
    return jsonResponse({
      configured: false,
      prices: {},
      message: 'Amazon Creators API credentials are not configured.'
    }, 503, { 'cache-control': 'no-store' });
  }

  const requestUrl = new URL(request.url);
  const cacheKey = new Request(`${requestUrl.origin}/__edge-cache/amazon-prices-v1`, { method: 'GET' });
  const cache = caches.default;
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  try {
    const token = await getAccessToken(env);
    const marketplace = env.AMAZON_MARKETPLACE || 'www.amazon.com';
    const response = await fetch('https://creatorsapi.amazon/catalog/v1/getItems', {
      method: 'POST',
      headers: {
        authorization: `Bearer ${token}`,
        'content-type': 'application/json',
        'x-marketplace': marketplace
      },
      body: JSON.stringify({
        itemIds: PRODUCT_ASINS,
        itemIdType: 'ASIN',
        marketplace,
        partnerTag: env.AMAZON_ASSOCIATE_TAG,
        resources: [
          'offersV2.listings.price',
          'offersV2.listings.availability',
          'offersV2.listings.isBuyBoxWinner'
        ]
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Amazon Creators API error', response.status, errorText.slice(0, 1000));
      return jsonResponse({ configured: true, prices: {}, upstreamStatus: response.status }, 502, { 'cache-control': 'no-store' });
    }

    const payload = await response.json();
    const updatedAt = new Date().toISOString();
    const items = payload?.itemsResult?.items || [];
    const prices = {};

    for (const item of items) {
      const normalized = normalizeItem(item, updatedAt);
      if (normalized.asin) prices[normalized.asin] = normalized;
    }

    const output = jsonResponse({ configured: true, updatedAt, prices }, 200, {
      'cache-control': 'public, max-age=300, s-maxage=3600'
    });

    context.waitUntil(cache.put(cacheKey, output.clone()));
    return output;
  } catch (error) {
    console.error('Amazon price endpoint failure', error);
    return jsonResponse({ configured: true, prices: {}, error: 'price_lookup_failed' }, 502, { 'cache-control': 'no-store' });
  }
}