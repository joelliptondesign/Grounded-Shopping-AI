/* Authored renderer preparation. Conversation orchestration stays in the app. */
(function (root) {
  function prepareBlocks(blocks, products, fb, actions, defaults) {
    const BY_ID = products;
    const { SHORTLIST, PROGRAM, CMP_ROWS, SPECS, SPEC_FALLBACK, SUGGESTIONS, SERVICE, SCRIPTED } = defaults;
    return blocks.map((b, bi) => ({
      upColor: fb[bi] === "up" ? "#0f1111" : "#9a9fa0",
      downColor: fb[bi] === "down" ? "#0f1111" : "#9a9fa0",
      onUp: () => actions.feedback(bi, "up"),
      onDown: () => actions.feedback(bi, "down"),
      kind: b.kind,
      isUser: b.kind === "user",
      isProgress: b.kind === "progress",
      isDots: b.kind === "dots",
      isText: b.kind === "text",
      isRecs: b.kind === "recs",
      isCompare: b.kind === "compare",
      isSuggest: b.kind === "suggest",
      products: b.kind === "recs" ? (b.items || SHORTLIST.map(id => ({ id }))).map(it => {
        const p = BY_ID[it.id];
        return {
        role: it.role || p.role,
        name: p.name,
        rating: p.rating.toFixed(1),
        stars: (p.rating / 5 * 100).toFixed(1) + "%",
        reviews: "(" + p.reviews + ")",
        dollars: p.dollars,
        cents: p.cents,
        list: p.list,
        hasList: !!p.list,
        program: PROGRAM(p.days),
        deliveryType: p.service ? "delivery with haul-away service" : "delivery",
        deliveryDate: p.service && p.window ? p.delivery + ", " + p.window : p.delivery,
        prime: p.prime,
        why: it.why || p.why,
        h: p.art.h,
        cover: p.art.cover,
        band: p.art.band,
        base: p.art.base,
        slotId: "shot-" + p.id,
        photo: p.photo || "",
        showMore: !b.more,
        onMore: () => actions.more(it.role || p.role, b),
        onCart: () => actions.cart(p.id)
        };
      }) : [],
      cmpAPhoto: b.kind === "compare" ? ((BY_ID[b.pair[0]] || {}).photo || "") : "",
      cmpBPhoto: b.kind === "compare" ? ((BY_ID[b.pair[1]] || {}).photo || "") : "",
      cmpASlot: b.kind === "compare" ? "cmp-a-" + b.pair[0] : "",
      cmpBSlot: b.kind === "compare" ? "cmp-b-" + b.pair[1] : "",
      cmpAName: b.kind === "compare" ? ((b.names || [])[0] || (BY_ID[b.pair[0]] || {}).short || "") : "",
      cmpBName: b.kind === "compare" ? ((b.names || [])[1] || (BY_ID[b.pair[1]] || {}).short || "") : "",
      cmpRows: b.kind !== "compare" ? [] : (b.rows || CMP_ROWS.map(label => ({
        label,
        a: (SPECS[b.pair[0]] || SPEC_FALLBACK)[label] || "—",
        b: (SPECS[b.pair[1]] || SPEC_FALLBACK)[label] || "—"
      }))).map((r, i) => ({
        label: r.label,
        a: r.a,
        b: r.b,
        border: i === 0 ? "none" : "1px solid #eceded"
      })),
      suggestions: b.kind === "suggest" ? (b.items || SUGGESTIONS).map(s => ({
        label: s,
        onPick: e => {
          actions.reply(s, e);
        }
      })) : [],
      text: b.text,
      parts: (b.parts || []).map(p => ({ t: p.t, weight: p.b ? 700 : 400 })),
      isService: b.kind === "service",
      isFeedback: b.kind === "feedback",
      // Live product detail reuses this block with backend-supplied fact rows.
      svcHeading: b.heading || SERVICE.heading,
      svcNote: b.note || SERVICE.note,
      svcRows: b.kind === "service" ? (b.rows || SERVICE.rows).map((r, i) => ({
        label: r.label,
        value: r.value,
        color: r.color,
        border: i === 0 ? "none" : "1px solid #eceded"
      })) : [],
      steps: b.kind === "progress"
        ? (b.steps || SCRIPTED.steps).slice(0, b.active + 1).map((label, i) => ({
            label,
            dot: i === b.active ? "#0f6fc5" : "#d5d9d9",
            color: i === b.active ? "#0f1111" : "#8d9192",
            weight: i === b.active ? 500 : 400
          }))
        : []
    }));
  }
  root.RufusRenderer = { prepareBlocks };
  if (typeof module !== "undefined") module.exports = root.RufusRenderer;
})(globalThis);
