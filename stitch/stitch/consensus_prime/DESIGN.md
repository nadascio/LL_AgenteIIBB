# Design System Strategy: The Architectural Authority

## 1. Overview & Creative North Star
**The Creative North Star: "The Digital Atelier of Trust"**

For Lisicki Litvin (LL), we are moving beyond the "corporate template" and into the realm of **Architectural Precision**. Accounting and law are disciplines of exactness, layers of evidence, and structured thought. This design system reflects that by treating the screen not as a flat surface, but as a series of curated, layered planes. 

The aesthetic is **Editorial Professionalism**: we use aggressive whitespace, intentional asymmetry in layouts to guide the eye, and a "Tonal Layering" approach that replaces crude lines with sophisticated depth. The goal is to make complex data feel breathable and high-stakes decisions feel calm.

---

## 2. Colors & Surface Philosophy
The palette is rooted in `primary` (#001e40), a deep, commanding navy that signals heritage, balanced by a sophisticated range of architectural greys.

### The "No-Line" Rule
Traditional 1px borders are strictly prohibited for sectioning. They clutter the interface and create "visual noise" that tires the user. Instead, define boundaries through:
*   **Background Shifts:** Use `surface` as your base, transitioning to `surface-container-low` for secondary content areas.
*   **Tonal Transitions:** A `surface-container-highest` block sitting on a `surface` background creates a natural, sophisticated edge without a single line being drawn.

### Surface Hierarchy & Nesting
Treat the UI as a physical stack of fine stationery:
1.  **Base Layer:** `surface` (#f9f9fe) — The vast, clean canvas.
2.  **Mid-Layer:** `surface-container-low` (#f4f3f8) — Use this for sidebar navigation or secondary utility panels.
3.  **Top-Layer (The Content):** `surface-container-lowest` (#ffffff) — Reserved for the most critical data "cards" or "sheets" to make them pop forward.

### The "Glass & Gradient" Rule
To elevate the premium feel, use **Glassmorphism** for floating elements (like navigation bars or modal headers). 
*   **Token:** Use `surface` at 80% opacity with a `backdrop-filter: blur(20px)`.
*   **Signature Textures:** For Hero sections or primary CTAs, apply a subtle linear gradient from `primary` (#001e40) to `primary-container` (#003366) at a 135-degree angle. This adds "soul" and prevents the deep blues from feeling static.

---

## 3. Typography: The Editorial Scale
We utilize a dual-font strategy to balance authority with readability.

*   **Display & Headlines (Manrope):** Chosen for its geometric precision and modern "tech-law" feel. 
    *   `display-lg` (3.5rem): Use sparingly for high-impact landing statements.
    *   `headline-md` (1.75rem): The standard for section titles. Use tight letter-spacing (-0.02em) for a premium feel.
*   **Body & UI (Inter):** Chosen for its extreme legibility in data-heavy contexts.
    *   `body-md` (0.875rem): Your workhorse. Ensure a line-height of 1.5 to maintain "breathable" text blocks.
    *   `label-md` (0.75rem): Used for metadata and table headers. Always use `on-surface-variant` (#43474f) to create a clear hierarchy against body text.

---

## 4. Elevation & Depth
In this system, "Elevation" is a measure of light and tone, not shadows.

*   **The Layering Principle:** Depth is achieved by stacking. Place a `surface-container-lowest` card (Pure White) on top of a `surface-container-low` (Pale Grey) background. This creates a "soft lift."
*   **Ambient Shadows:** If a component must float (e.g., a dropdown or modal), use a shadow that is felt, not seen.
    *   *Shadow Specs:* `0px 12px 32px rgba(0, 30, 64, 0.06)`. Note the use of `primary` in the shadow color—this creates a more natural "ambient" light effect than black.
*   **The "Ghost Border" Fallback:** If a border is required (e.g., in a high-density data table), use `outline-variant` (#c3c6d1) at **20% opacity**. It should be a suggestion of a line, not a boundary.

---

## 5. Components

### Buttons (The Statement Components)
*   **Primary:** High-contrast `primary` (#001e40) background with `on-primary` (#ffffff) text. Corner radius: `sm` (0.125rem) for a sharp, legalistic feel.
*   **Secondary:** `secondary-container` (#e2e2e6) background. No border.
*   **Tertiary:** Text-only using `primary` (#001e40). Use for low-priority actions like "Cancel" or "Learn More."

### Input Fields (Precision Inputs)
*   **Style:** Minimalist. No background fill; only a bottom "Ghost Border" using `outline-variant`. 
*   **Focus State:** Transition the bottom border to `primary` (#001e40) with a 2px weight.
*   **Error State:** Use `error` (#ba1a1a) for the border and helper text.

### Cards & Lists (Data Containers)
*   **Constraint:** Forbid the use of divider lines between list items.
*   **Alternative:** Use 16px or 24px of vertical whitespace (Gap). For hover states, shift the background of the list item to `surface-container-high` (#e8e8ed).
*   **Cards:** Use `surface-container-lowest` (#ffffff) with a `lg` (0.5rem) roundedness to soften the corporate edge.

### Additional Signature Component: The "Data Sheet"
Specifically for accounting/law contexts, use a "Data Sheet" component: A large, white `surface-container-lowest` area with wide margins (48px+) and `headline-sm` titles. This mimics the feel of a physical, premium paper document.

---

## 6. Do's and Don'ts

### Do
*   **Do** use asymmetrical layouts (e.g., a wide left column for content and a narrow right column for metadata).
*   **Do** use `on-surface-variant` for "de-prioritized" text to keep the interface looking clean.
*   **Do** prioritize "Over-Spacing." If a section feels crowded, double the padding.

### Don't
*   **Don't** use pure black (#000000). Use `on-background` (#1a1c1f) for all "black" text to maintain a softer, high-end look.
*   **Don't** use standard 4px or 8px "Drop Shadows." They look "cheap." Use the Ambient Shadow spec.
*   **Don't** use icons with varying line weights. Use a consistent, light-weight (2px or 1.5px) icon set to match the Manrope/Inter aesthetic.