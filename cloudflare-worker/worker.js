/**
 * AYN Thor Tracker — Cloudflare Worker
 *
 * Environment variables to set in Cloudflare dashboard:
 *   GITHUB_TOKEN         — Personal Access Token with repo Contents write scope
 *   GITHUB_OWNER         — willow-source
 *   GITHUB_REPO          — thortracking.github.io
 *   ADMIN_PASSWORD_HASH  — df6fadca0a2ba94d6bc87a75cba9042639cbee4da84a2b6ca14f89720c467db4
 *   ALLOWED_ORIGIN       — https://willow-source.github.io
 */

const DATA_PATH = 'data/community.json';

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return corsResponse(null, 204, env);
    }

    const url = new URL(request.url);

    if (request.method === 'POST' && url.pathname === '/update') {
      return handleUpdate(request, env);
    }

    return corsResponse(JSON.stringify({ error: 'Not found' }), 404, env);
  }
};

async function handleUpdate(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return corsResponse(JSON.stringify({ error: 'Invalid JSON' }), 400, env);
  }

  const { variant, shipped_up_to, notes, updated_by, timestamp, password_hash } = body;

  // Server-side password check
  if (password_hash !== env.ADMIN_PASSWORD_HASH) {
    return corsResponse(JSON.stringify({ error: 'Unauthorized' }), 401, env);
  }

  // Validate fields
  if (!variant || !shipped_up_to || !updated_by) {
    return corsResponse(JSON.stringify({ error: 'Missing required fields' }), 400, env);
  }

  const allowedVariants = ['White Max', 'Black Pro', 'White Pro', 'Black Standard'];
  if (!allowedVariants.includes(variant)) {
    return corsResponse(JSON.stringify({ error: 'Invalid variant' }), 400, env);
  }

  const orderNum = String(shipped_up_to).replace(/[^0-9]/g, '');
  if (!orderNum || isNaN(parseInt(orderNum))) {
    return corsResponse(JSON.stringify({ error: 'Invalid order number' }), 400, env);
  }

  // Fetch current community.json from GitHub
  const fileUrl = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${DATA_PATH}`;
  const headers = {
    'Authorization': `token ${env.GITHUB_TOKEN}`,
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'AYNThorTracker/1.0'
  };

  const fileRes = await fetch(fileUrl, { headers });
  if (!fileRes.ok) {
    return corsResponse(JSON.stringify({ error: 'Failed to fetch data from GitHub: ' + fileRes.status }), 500, env);
  }

  const fileData = await fileRes.json();
  const sha = fileData.sha;
  const current = JSON.parse(atob(fileData.content.replace(/\n/g, '')));

  // Merge new entry
  const now = timestamp || new Date().toISOString();

  const variantIdx = current.variants.findIndex(v => v.name === variant);
  if (variantIdx >= 0) {
    current.variants[variantIdx].shipped_up_to = orderNum;
    current.variants[variantIdx].notes = notes || '';
    current.variants[variantIdx].updated = now;
  }

  current.history.push({
    variant,
    shipped_up_to: orderNum,
    notes: notes || '',
    updated_by,
    timestamp: now
  });

  current.last_updated = now;

  // Commit back to GitHub
  const newContent = btoa(unescape(encodeURIComponent(JSON.stringify(current, null, 2))));
  const commitRes = await fetch(fileUrl, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: `tracker: ${variant} shipped up to #${orderNum} [${updated_by}]`,
      content: newContent,
      sha
    })
  });

  if (!commitRes.ok) {
    const err = await commitRes.text();
    return corsResponse(JSON.stringify({ error: 'GitHub commit failed', detail: err }), 500, env);
  }

  return corsResponse(JSON.stringify({ ok: true, variant, shipped_up_to: orderNum }), 200, env);
}

function corsResponse(body, status, env) {
  const origin = env.ALLOWED_ORIGIN || '*';
  return new Response(body, {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type'
    }
  });
}
