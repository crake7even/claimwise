---
name: Assurance AI
colors:
  surface: '#f8f9fb'
  surface-dim: '#d9dadc'
  surface-bright: '#f8f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f6'
  surface-container: '#edeef0'
  surface-container-high: '#e7e8ea'
  surface-container-highest: '#e1e2e4'
  on-surface: '#191c1e'
  on-surface-variant: '#434654'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#f0f1f3'
  outline: '#737685'
  outline-variant: '#c3c6d6'
  surface-tint: '#0c56d0'
  primary: '#003d9b'
  on-primary: '#ffffff'
  primary-container: '#0052cc'
  on-primary-container: '#c4d2ff'
  inverse-primary: '#b2c5ff'
  secondary: '#585f6a'
  on-secondary: '#ffffff'
  secondary-container: '#dce3f0'
  on-secondary-container: '#5e6570'
  tertiary: '#004b59'
  on-tertiary: '#ffffff'
  tertiary-container: '#006477'
  on-tertiary-container: '#76e2ff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2ff'
  primary-fixed-dim: '#b2c5ff'
  on-primary-fixed: '#001848'
  on-primary-fixed-variant: '#0040a2'
  secondary-fixed: '#dce3f0'
  secondary-fixed-dim: '#c0c7d3'
  on-secondary-fixed: '#151c25'
  on-secondary-fixed-variant: '#404751'
  tertiary-fixed: '#afecff'
  tertiary-fixed-dim: '#48d7f9'
  on-tertiary-fixed: '#001f27'
  on-tertiary-fixed-variant: '#004e5d'
  background: '#f8f9fb'
  on-background: '#191c1e'
  surface-variant: '#e1e2e4'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 64px
  max-width: 1280px
---

## Brand & Style
The brand personality is authoritative yet approachable, designed to instill confidence and clarity in the complex world of insurance. The target audience includes policyholders and agents who require precision and speed. 

The design style is **Corporate / Modern** with a heavy emphasis on **Minimalism**. The UI is characterized by generous whitespace, a high-key brightness, and a lack of visual clutter. By using a "Paper & Ink" philosophy, the system ensures that information density is managed through structural hierarchy rather than decorative elements. The emotional response should be one of "effortless reliability"—the user should feel the AI is an expert tool that is both transparent and highly efficient.

## Colors
The palette is rooted in "Insurance Blue"—a shade that signals stability and trust. 

- **Primary**: A deep, vibrant blue used for core actions and brand presence.
- **Secondary**: A very light, tinted blue used for selection states and soft backgrounds to differentiate sections from the pure white base.
- **Neutral**: A range of cool grays used for borders and secondary text.
- **Functional**: Success (Green), Warning (Amber), and Error (Red) colors should be muted but clear to maintain the professional tone.

The background remains predominantly pure white to maintain an airy, high-contrast feel, using light gray or light blue only to define container boundaries or grouped content.

## Typography
The typography system uses **Inter** for its exceptional legibility and neutral, professional character. 

- **Headlines**: Use SemiBold weights to provide a strong structural anchor. Large headlines use slight negative letter-spacing to appear tighter and more "designed."
- **Body Text**: Optimized for long-form reading of policy documents and AI chat transcripts. Line heights are kept generous (1.5x) to enhance the "airy" feel.
- **Labels**: Small caps or bold weights are used for metadata and form labels to ensure they are distinct from user input.

## Layout & Spacing
The design system utilizes a **Fixed Grid** on desktop and a **Fluid Grid** on mobile. 

- **Desktop**: A 12-column grid with a 24px gutter. Content is centered with a max-width of 1280px to prevent excessive line lengths in chat interfaces.
- **Mobile**: A 4-column fluid grid with 16px margins. 
- **Rhythm**: All spacing follows a 4px/8px baseline shift. Vertical rhythm is strictly enforced to maintain a "structured" look. Large components (like claim cards) use 32px or 48px of padding to emphasize the premium, airy quality of the brand.

## Elevation & Depth
Depth is created using **Low-contrast outlines** and **Tonal layers** rather than heavy shadows.

- **Level 0 (Background)**: Pure white (#FFFFFF).
- **Level 1 (Cards/Containers)**: White background with a 1px solid border (#DFE1E6). No shadow.
- **Level 2 (Interaction/Popovers)**: White background with a very soft, diffused shadow (0px 4px 12px rgba(9, 30, 66, 0.08)) to indicate temporary overlay status.
- **Separation**: Use subtle background shifts (to #F4F5F7) to distinguish between a side navigation bar and the primary workspace.

## Shapes
The shape language is **Rounded**, conveying friendliness without appearing juvenile. 

- **Standard Components**: Buttons, inputs, and small cards use a 0.5rem (8px) radius.
- **Large Containers**: Hero sections or main chat windows use 1rem (16px) to soften the overall appearance of the screen.
- **Icons**: Use a consistent corner radius of 2px for custom iconography to match the "soft but professional" aesthetic.

## Components
- **Buttons**: Primary buttons are solid Blue with white text. Secondary buttons use a Light Blue fill with Primary Blue text. Tertiary buttons are text-only with a bold weight.
- **Inputs**: Use a 1px border (#DFE1E6). On focus, the border turns Primary Blue with a 2px outer glow of the same color at 20% opacity.
- **AI Chat Bubbles**: The Assistant bubble uses the Secondary Blue fill with no border. The User bubble uses a light neutral gray fill. This differentiates the "voice" of the AI from the human.
- **Cards**: Minimalist with 24px padding, a 1px border, and no shadow unless hovered.
- **Chips**: Pill-shaped with a light gray background, used for policy tags or suggested questions.
- **Progress Bars**: Thick, rounded bars with the Primary Blue color, used for showing claim completion or document processing status.