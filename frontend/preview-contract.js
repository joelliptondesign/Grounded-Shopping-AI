/* Explicit synthetic example contract; never fills missing data from Demo. */
(function (root) {
  function validate(input) {
    const fail = message => { throw new Error(message); };
    if (!input || typeof input.id !== 'string' || !Array.isArray(input.products) || !Array.isArray(input.blocks)) fail('Expected id, products and blocks');
    const example = JSON.parse(JSON.stringify(input));
    const products = Object.create(null);
    for (const p of example.products) {
      if (!p || typeof p.id !== 'string' || !p.id || Object.hasOwn(products, p.id)) fail('Invalid or duplicate product ID');
      products[p.id] = p;
    }
    const requireProduct = id => { if (!Object.hasOwn(products, id)) fail('Unknown product: ' + id); return products[id]; };
    for (const b of example.blocks) {
      if (!b || !['user', 'text', 'recs', 'compare', 'suggest', 'feedback', 'service', 'progress', 'dots'].includes(b.kind)) fail('Unsupported block kind');
      if (b.kind === 'recs') {
        if (!Array.isArray(b.items) || typeof b.more !== 'boolean') fail('Recommendations require items and explicit more flag');
        for (const item of b.items) {
          if (!item || typeof item.role !== 'string' || !item.role || typeof item.why !== 'string' || !item.why) fail('Card requires role and explanation');
          const p = requireProduct(item.id);
          for (const key of ['name', 'dollars', 'cents', 'list', 'delivery', 'photo']) if (typeof p[key] !== 'string') fail('Card product requires ' + key);
          if (!Number.isFinite(p.rating) || !Number.isFinite(p.reviews) || !Number.isFinite(p.days) || typeof p.service !== 'boolean' || typeof p.prime !== 'boolean' || !p.art || typeof p.art !== 'object') fail('Card requires explicit decorative fields');
          if (p.service && typeof p.window !== 'string') fail('Service card requires delivery window');
        }
      }
      if (b.kind === 'compare') {
        if (!Array.isArray(b.pair) || b.pair.length !== 2 || !Array.isArray(b.names) || b.names.length !== 2 || !b.names.every(n => typeof n === 'string' && n) || !Array.isArray(b.rows)) fail('Comparison requires two products, names and rows');
        b.pair.forEach(id => { const p = requireProduct(id); if (typeof p.photo !== 'string') fail('Comparison product requires photo'); });
        if (!b.rows.every(r => r && ['label','a','b'].every(k => typeof r[k] === 'string'))) fail('Invalid comparison row');
      }
      if (b.kind === 'suggest' && (!Array.isArray(b.items) || !b.items.every(s => typeof s === 'string' && s))) fail('Replies require explicit labels');
      if (b.kind === 'text' && (!Array.isArray(b.parts) || !b.parts.every(p => p && typeof p.t === 'string'))) fail('Text requires parts');
      if (b.kind === 'user' && typeof b.text !== 'string') fail('User block requires text');
      if (b.kind === 'service' && (typeof b.heading !== 'string' || !b.heading || typeof b.note !== 'string' || !b.note || !Array.isArray(b.rows) || !b.rows.every(r => r && ['label','value','color'].every(k => typeof r[k] === 'string')))) fail('Service requires heading, note and explicit rows');
      if (b.kind === 'progress' && (!Array.isArray(b.steps) || !b.steps.every(s => typeof s === 'string') || !Number.isInteger(b.active))) fail('Progress requires steps and active index');
    }
    return { id: example.id, blocks: example.blocks, products };
  }
  root.RufusPreview = { validate };
  if (typeof module !== 'undefined') module.exports = root.RufusPreview;
})(globalThis);
