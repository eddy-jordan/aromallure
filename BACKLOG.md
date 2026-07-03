# Backlog — Deferred Features

## 1. Real Payment Processing (Phase 6)

**Current state:** Checkout creates a real Order with status "Pending."
No money actually changes hands.

**Planned approach:**
- Provider: Stripe (decided)
- Use Stripe test/sandbox mode throughout development
- Checkout redirects to Stripe-hosted payment page
- Order status flips Pending -> Paid via a Stripe webhook
- Build in steps: setup → checkout redirect → return handling → webhook → testing

---

## Previously Considered, Now Dropped

**Email verification at signup** — decided not to implement. Signup
logs users in immediately without any verification step. Order
confirmation emails still send via Resend SMTP when RESEND_API_KEY
is set in the environment.
