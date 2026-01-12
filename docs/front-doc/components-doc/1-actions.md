# React AI Actions
URL: /ai/actions
React AI actions component with icon button toolbar and optional tooltips for message interactions

Those little icon buttons under AI messages—copy, regenerate, thumbs up/down—this is how you build them. Actions is your container, Action is each button. Pass a tooltip and users get a nice hover hint. Icons go as children, screen reader text is handled automatically via the label or tooltip. We use ghost buttons by default so they're subtle until hovered. Drop this under MessageContent or wherever you need quick actions. Simple pattern, but you'll use it everywhere in chat UIs.

### Actions component preview

<AIPreview path="actions" />

## Installation

<Installer packageName="actions" />

## More React AI components

Explore other AI components for Next.js chat interfaces:

<Cards>
  <Card
    href="/ai/message"
    title="React AI Message"
    description="Chat message bubbles"
  />
  <Card
    href="/ai/toolbar"
    title="React AI Toolbar"
    description="Canvas action toolbar"
  />
  <Card
    href="/ai/confirmation"
    title="React AI Confirmation"
    description="Action confirmation UI"
  />
  <Card
    href="/ai/conversation"
    title="React AI Conversation"
    description="Chat container"
  />
  <Card
    href="/ai/suggestion"
    title="React AI Suggestion"
    description="Quick reply buttons"
  />
  <Card
    href="/ai/branch"
    title="React AI Branch"
    description="Message versioning"
  />
</Cards>

## Actions component FAQ

<Accordions type="single">
  <Accordion id="actions-tooltip" title="How do tooltips work?">
    Pass tooltip prop to Action and it wraps the button in TooltipProvider/Tooltip automatically. No tooltip prop means just a plain button. The tooltip text also becomes the screen reader label if you don't set label separately.
  </Accordion>

  <Accordion id="actions-styling" title="Can I customize button appearance?">
    Action takes all Button props—variant, size, className. Default is ghost variant and sm size. The muted-foreground color on hover becomes foreground, keeping things subtle.
  </Accordion>

  <Accordion id="actions-accessibility" title="How is accessibility handled?">
    Screen reader text comes from label prop, or falls back to tooltip. It's in a sr-only span so the button has proper accessible name even though it just shows an icon.
  </Accordion>

  <Accordion id="actions-layout" title="How do I arrange multiple actions?">
    Wrap them in Actions container—it's a flex row with gap-1. Add your Action buttons as children. They'll line up horizontally with consistent spacing.
  </Accordion>

</Accordions>