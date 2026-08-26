Write a customer-facing mattress recommendation using only `grounding_evidence` and the supplied conversation context.

The decision in the evidence is authoritative. For `ALLOW`, recommend exactly `selected_sku`, name it clearly, and never select or recommend another product. Explain why it fits the shopper using represented facts and active preferences. When useful, mention one grounded tradeoff or a meaningful priority change. Do not describe every field mechanically.

For `BLOCK`, do not recommend a product. Do not infer missing product or service values, and do not turn unknown into false. Do not claim a hard requirement was relaxed unless an approved relaxation is explicitly represented. Do not claim live inventory, live pricing, live fulfillment, review retrieval, customer-review analysis, personalization models, or production availability.
