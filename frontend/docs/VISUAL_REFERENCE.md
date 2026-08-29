# Rufus Visual Reference

## Design direction

Follow the current Amazon shopping assistant UI as closely as practical.

Do not create an “Amazon-inspired” redesign. The goal is a believable Amazon consumer experience.

## Overall visual language

- White background
- Minimal decorative UI
- Dark gray / black body text
- Amazon blue for links and interactive text
- Amazon yellow for primary commerce actions such as Add to Cart
- Soft gray borders around cards
- Large amounts of whitespace
- Simple, restrained rounded corners
- Minimal shadow use
- Familiar Amazon product information hierarchy

## Header

Mobile references show:
- Back / collapse control on the left
- Assistant branding near the left
- History / refresh-style action on the right
- Overflow menu on the far right

Use `rufus` branding in place of the source assistant branding.

Keep the header visually lightweight.

## Cold start

The cold-start state is intentionally sparse:
- Header
- Large “How can I help you today?” prompt
- Large persistent composer near the bottom
- No dashboard-like panels
- No decorative AI artwork

The empty space is part of the design.

## Composer

The composer should feel native to Amazon:
- White input surface
- Light gray border
- Rounded rectangle
- Placeholder: “Ask a shopping question”
- Plus button on the left
- Send or microphone action on the right depending on state
- Fixed / sticky near the bottom
- Mobile safe-area aware

## User messages

- Right aligned
- Light gray rounded bubble
- Dark text
- Compact padding
- No avatar

## Rufus responses

Rufus responses generally sit directly on the white page rather than inside a chat bubble.

Use:
- Dark body text
- Bold emphasis for important attributes
- Amazon blue for links
- Strong vertical spacing between response text and structured content

## Product cards

Product cards should closely resemble Amazon shopping cards.

Typical hierarchy:
- Product image on left
- Product name on right
- Star rating and review count
- Price
- Previous / list price when relevant
- Delivery information
- Prime treatment when relevant
- Yellow Add to Cart button
- Light gray 1px border
- Rounded corners

Outside or below the card, Rufus may add a short explanation of why the product matches the shopper.

Avoid inventing glossy AI-specific card chrome.

## Section headings

Examples:
- “Best match”
- “Strong alternatives”
- “Compare your top options”
- “Delivery and setup”

Use bold dark headings and optional Amazon-blue “see more” links.

## Loading / progress behavior

Two source loading patterns are useful.

### Progress steps

Show brief, observable actions such as:
- Understanding what matters to you
- Checking matching mattresses
- Verifying delivery options
- Preparing recommendations

Completed or inactive steps can use a light gray dot.

The active step uses an Amazon-blue dot.

Do not expose chain-of-thought or hidden model reasoning.

### Compact loading animation

Use a small horizontal cluster of circular dots in dark-to-light blue.

This can appear when a lighter-weight response is generating.

## Motion

Keep transitions subtle and consumer-product-like:
- Fade / slide in new response content
- Progress steps update one at a time
- Skeleton cards may appear shortly before final card content
- No dramatic AI animation
- No typing effect for long generated prose

## Desktop

Mobile is the primary design target.

For desktop later, preserve the same visual language in a centered or right-side shopping drawer rather than redesigning the experience.
