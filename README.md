# Aromallure — "Elegance in a Bottle"

> Known limitations and deferred features (real payments, email
> verification) are tracked in BACKLOG.md, not repeated here.

## How to Run Locally

1. Install dependencies:
   pip install -r requirements.txt

2. Run the development server:
   python manage.py runserver

3. Open http://127.0.0.1:8000/

## Admin Login (store owner)
   URL: http://127.0.0.1:8000/admin/
   username: admin
   password: admin12345

## What's New: Branding + Homepage Entrance

### Real Brand Identity
The store is now officially "Aromallure" (renamed from the placeholder
"Maison Lumière") — settings.SITE_NAME updated, which propagates
everywhere automatically via the store_name context processor.

### Logo
The uploaded logo was processed into two versions:
- A cropped icon-only mark (bottle + laurel wreath, no text), with the
  white background removed and replaced with true transparency, placed
  beside the "AROMALLURE" wordmark in the navbar
- A full logo (icon + script wordmark + tagline), also background-
  removed, used for the homepage entrance below

Both were verified by compositing onto solid dark and light test
backgrounds to confirm there's no leftover white halo around the
line art before they were used anywhere in the site.

### Homepage Entrance "Flare"
Every time the homepage specifically (not other pages) is opened, the
full logo briefly appears center-screen with a soft scale/fade-in, a
gold radial glow, a diagonal light shimmer sweep, and a thin gold line
drawing outward beneath it — then the whole overlay dissolves to
reveal the page underneath, whose hero section gently rises into view
as the curtain lifts.

Built to be resilient and accessible:
- Respects prefers-reduced-motion — users with that OS setting skip
  the entrance instantly, no animation overhead
- Works correctly even with JavaScript disabled: the CSS animation
  itself fades the overlay and disables its pointer-events via
  animation-fill-mode — JavaScript only removes the now-invisible
  element from the DOM afterward as cleanup, it isn't required for
  the page to become usable
- Scoped to the homepage only via an `is_home` context flag, not a
  sitewide overlay

## Verified Before Delivery
- Confirmed the entrance overlay appears on the homepage and is
  absent on every other page (product detail, cart, login, etc.)
- Confirmed both logo images load correctly as static files
- Confirmed the brand name change ("Aromallure") appears correctly
  across the navbar, footer, and login page subtitle
- Ran the full signup -> add to cart -> checkout -> confirmation flow
  again after these changes to confirm nothing broke
- Calculated decorative-image contrast for the line-art logo against
  both theme backgrounds (passes the 3:1 minimum for non-text content)
- Removed all test data created during verification afterward

## Files Added/Changed
- static/shop/img/logo-icon.png — new, transparent navbar icon mark
- static/shop/img/logo-full.png — new, transparent full logo for the
  entrance animation
- templates/base.html — navbar logo, entrance overlay markup
  (homepage-only), cleanup script
- static/shop/css/style.css — brand/logo layout, full entrance
  animation system (keyframes, reduced-motion handling)
- shop/views.py — product_list_view now passes is_home=True
- perfume_store/settings.py — SITE_NAME changed to "Aromallure",
  DEFAULT_FROM_EMAIL domain updated to match

## Still To Come (see BACKLOG.md)
- Phase 6: Real payment processing (Stripe)
- Email verification at signup
