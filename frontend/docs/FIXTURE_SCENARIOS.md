# Rufus Fixture Scenarios

## Purpose

These fixtures exist to create realistic screenshots and short portfolio videos.

They should feel like one continuous shopping journey rather than disconnected demos.

Use deterministic fixture data and scripted timing for now.

---

# Scenario 1 — Initial recommendation

## Customer

> We need a queen mattress. We both sleep hot, my wife likes something a little softer than I do, and I'd like to stay around $1,800.

## Progress sequence

1. Understanding what matters to you
2. Checking queen mattresses
3. Comparing cooling and comfort
4. Preparing recommendations

Use realistic timing rather than instant output.

## Rufus response

Keep the framing short.

Example direction:

> I found a few options that balance cooling, comfort, and your budget. This one is the strongest overall fit for both of you.

## Structured output

Show:
- 1 emphasized “Best match”
- 2 additional alternatives
- Amazon-style product cards
- 2–3 concise “Why it fits” reasons for the top option

Top reasons should map directly to the shopper’s stated needs:
- Strong cooling
- Medium / medium-soft feel
- Good motion isolation
- Near preferred budget

Do not imply mathematical certainty.

---

# Scenario 2 — Adaptive comparison

## Customer

> Compare the first two.

## Loading

Use the compact blue-dot animation or a very short progress state.

## Result

Switch from recommendation cards into a mobile comparison view.

Compare only fields relevant to this shopper:
- Price
- Feel / firmness
- Cooling
- Motion isolation
- Delivery
- Trial / return information if represented

Add a short Rufus summary above or below:

> The first option is the better fit if cooling matters most. The second saves money and is slightly softer.

Keep the comparison scannable.

Do not dump every available product specification.

---

# Scenario 3 — Grounded service lookup

## Customer

> Will they set it up and take away my old mattress?

## Progress sequence

1. Checking delivery services
2. Verifying setup and haul-away for your location

This scenario is important because it demonstrates a real failure mode from earlier AI shopping experiences.

## Result

Rufus should clearly distinguish what is verified.

Example direction:

> Yes. For this mattress and your delivery location, room-of-choice delivery and setup are available. Old-mattress haul-away is also available with the selected delivery service.

Show a lightweight service summary:
- Room-of-choice delivery — Available
- Setup — Available
- Old mattress haul-away — Available

Optionally include a small “Verified for this item and delivery location” treatment.

Do not fabricate service availability outside the fixture.

---

# Scenario 4 — Preference change and recovery

## Customer

> That's a little more than I want to spend. Can we keep the cooling but get closer to $1,400?

## Progress sequence

1. Updating your budget
2. Keeping cooling as a priority
3. Checking better-value options

## Result

Preserve the previous shopper context.

Do not restart with a new questionnaire.

Show:
- Updated recommendation cards
- One concise sentence explaining what changed
- A visible trade-off where appropriate

Example direction:

> These stay closer to $1,400 while keeping strong cooling. The main trade-off is slightly less motion isolation than the original top pick.

This demonstrates recovery and preference persistence.

---

# Fixture product requirements

Create a small set of plausible mattress fixtures with:
- Brand
- Product name
- Image
- Price
- List price where useful
- Rating
- Review count
- Size availability
- Firmness / feel
- Cooling
- Motion isolation
- Material / construction
- Delivery date
- Prime status
- Setup availability
- Haul-away availability
- Short grounded explanation text

The data should be internally consistent across recommendation, comparison, service lookup, and recovery.

Use realistic Amazon-style naming and values.

Do not use obviously fake placeholders such as “Mattress A” or “Product 1”.
