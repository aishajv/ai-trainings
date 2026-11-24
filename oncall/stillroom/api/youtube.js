// Server-side proxy to the YouTube Data API.
// The key lives in Vercel (env var YOUTUBE_API_KEY) and never reaches the browser.
// Every call writes one JSON log line, so on-call tools can read health from Vercel logs.

const ALLOWED = new Set(['search', 'videos']);

module.exports = async (req, res) => {
  const started = Date.now();
  const { endpoint, ...params } = req.query || {};
  const log = (level, fields) =>
    console[level](JSON.stringify({ service: 'stillroom', route: '/api/youtube', endpoint, ...fields, ms: Date.now() - started }));

  if (!ALLOWED.has(endpoint)) {
    log('warn', { event: 'bad_endpoint', status: 400 });
    return res.status(400).json({ error: { message: `unknown endpoint '${endpoint}'`, errors: [{ reason: 'badEndpoint' }] } });
  }

  const key = process.env.YOUTUBE_API_KEY;
  if (!key) {
    log('error', { event: 'youtube_error', status: 500, reason: 'keyMissing', message: 'YOUTUBE_API_KEY is not set' });
    return res.status(500).json({ error: { message: 'server has no YouTube key', errors: [{ reason: 'keyMissing' }] } });
  }

  const url = new URL('https://www.googleapis.com/youtube/v3/' + endpoint);
  for (const [k, v] of Object.entries(params)) if (v != null && v !== '') url.searchParams.set(k, v);
  url.searchParams.set('key', key);

  let upstream;
  try {
    upstream = await fetch(url);
  } catch (e) {
    log('error', { event: 'youtube_error', status: 502, reason: 'network', message: String(e && e.message) });
    return res.status(502).json({ error: { message: "couldn't reach YouTube", errors: [{ reason: 'network' }] } });
  }

  const body = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    const first = (body.error && body.error.errors && body.error.errors[0]) || {};
    log('error', {
      event: 'youtube_error',
      status: upstream.status,
      reason: first.reason || 'unknown',
      message: (body.error && body.error.message) || upstream.statusText,
    });
  } else {
    log('log', { event: 'youtube_ok', status: upstream.status, items: (body.items || []).length });
  }
  res.setHeader('Cache-Control', 'no-store');
  return res.status(upstream.status).json(body);
};
