# Design System Strategy: Enterprise Cyberpunk

## 1. Overview & Creative North Star: The Kinetic Guardian
This design system is not a standard utility framework; it is a high-performance instrument. To achieve the "Enterprise Cyberpunk" aesthetic, we move away from the cluttered, neon-soaked tropes of the genre and toward a "Kinetic Guardian" philosophy. This means the UI feels like a silent, high-speed sentinel—authoritative, deep-layered, and lightning-fast.

We break the "template" look by favoring **intentional asymmetry** and **tonal depth** over rigid grids and lines. Imagine a command center where information doesn't just sit on a screen but floats in a pressurized void. Every element is a tactical choice.

## 2. Colors: The Void and the Pulse
Our palette is built on the tension between the absolute stability of the "Deep Slate" foundations and the high-energy "Electric Blue" pulses.

*   **Foundation:** We use `surface` (#0e0e0e) as our absolute base. It is the void.
*   **The "No-Line" Rule:** Under no circumstances are you to use 1px solid borders to separate sections. Structure must be defined through background shifts. A `surface-container-low` section sitting against a `surface` background is all the definition the eye needs.
*   **Surface Hierarchy & Nesting:** Think of the UI as a physical stack. 
    *   **Level 0:** `surface` (The deep background).
    *   **Level 1:** `surface-container-low` (Navigation rails or side panels).
    *   **Level 2:** `surface-container` (Main content cards).
    *   **Level 3:** `surface-container-highest` (Modals or floating action elements).
*   **The "Glass & Gradient" Rule:** To provide "soul," primary CTAs and hero elements should utilize a subtle linear gradient from `primary` (#6dddff) to `primary_container` (#00d2fd). For floating panels, use a semi-transparent `surface_variant` with a heavy `backdrop-blur` (20px+) to create a sophisticated glass effect.

## 3. Typography: Editorial Authority
We use a high-contrast typographic scale to differentiate between "System Data" and "Executive Overview."

*   **Display & Headlines:** We utilize **Space Grotesk**. Its geometric quirks provide the "cutting-edge" tech feel without looking like a toy. Use `display-lg` for hero moments with tight letter-spacing (-2%) to feel aggressive and fast.
*   **Body & Labels:** We use **Inter**. It is the workhorse of clarity. Keep `body-md` as your standard for data density.
*   **Technical Edge:** For code snippets, IP addresses, or status logs, use **JetBrains Mono**. It signals "Enterprise" through its professional, developer-centric legibility.

The hierarchy should feel editorial; large, bold headlines should be paired with significantly smaller, high-contrast labels to create a sense of scale and importance.

## 4. Elevation & Depth: Tonal Layering
Depth in this system is achieved through light and layering, never through heavy drop shadows.

*   **The Layering Principle:** Avoid shadows for static elements. Instead, nest containers using the surface tiers. A `surface-container-lowest` card on a `surface-container-low` section creates a natural "recessed" look.
*   **Ambient Shadows:** For floating elements (Modals, Tooltips), use a hyper-diffused shadow.
    *   *Token:* `0px 20px 40px rgba(0, 0, 0, 0.4)`. The shadow should feel like a soft ambient occlusion, not a dark smudge.
*   **The "Ghost Border" Fallback:** If a layout requires a container to be hyper-distinct (e.g., a critical security alert), use a "Ghost Border." This is a 1px stroke using the `outline-variant` token at **15% opacity**. It should be felt, not seen.
*   **Glow States:** On hover, primary interactive elements should emit a soft bloom. Use the `primary` color with a 10px blur at low opacity (20%) to simulate a hardware interface "waking up."

## 5. Components

### Buttons
*   **Primary:** Solid `primary` fill with `on-primary` text. No border. On hover, apply a `primary_dim` glow.
*   **Secondary:** Ghost style. No background, 1px `outline-variant` (Ghost Border rule), with `primary` text.
*   **Tertiary:** Text-only using `primary` color, strictly for low-priority actions.

### Input Fields
*   **Styling:** Forbid the "box" look. Use `surface-container-high` as the background with a `md` (0.375rem) corner radius. 
*   **Focus State:** Transition the background to `surface-container-highest` and add a 1px "Ghost Border" of `primary`.

### Cards & Lists
*   **Forced Spacing:** Use the `xl` (0.75rem) spacing token to separate content. 
*   **No Dividers:** Never use horizontal lines. Use a 4px vertical background shift or a slight change in the `surface-container` tier to denote a new list item.

### Terminal Widgets (Custom Component)
*   A dedicated container for "High-Performance" logs.
*   **Background:** `surface-container-lowest` (pure black #000000).
*   **Typography:** JetBrains Mono, `label-sm`.
*   **Accent:** Use `secondary` (#00fc40) for success pings and `error` (#ff716c) for failed handshakes.

## 6. Do’s and Don’ts

### Do:
*   **Do** use extreme white space. High-performance brands need room to breathe.
*   **Do** use `secondary` (#00fc40) exclusively for "System Go" or "Security Active" states. 
*   **Do** embrace the asymmetry. Aligning a headline to the far left while the content sits in a staggered grid to the right creates a custom, high-end feel.

### Don’t:
*   **Don’t** use pure grey (#888). Use `on-surface-variant` to keep the cool, slate-toned integrity of the brand.
*   **Don’t** use rounded corners larger than `xl` (0.75rem). The brand should feel sharp and precise, not "bubbly."
*   **Don’t** use 100% opaque borders. It breaks the immersion of the layered "glass" environment.

This system is built for speed. Every pixel must justify its existence. If it doesn't contribute to the feeling of security or performance, remove it.