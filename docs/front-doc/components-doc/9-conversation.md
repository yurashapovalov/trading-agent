# React AI Conversation
URL: /ai/conversation
React AI conversation component with auto-scroll, empty state, and scroll-to-bottom button for chat interfaces

Getting scroll behavior right in a chat UI is surprisingly annoying. You want it to stick to the bottom as new messages stream in, but not fight the user when they scroll up to read something. This component handles all that. It uses use-stick-to-bottom under the hood, which is battle-tested for this exact use case. When the user scrolls up, a little "scroll to bottom" button appears so they can jump back down. There's also a built-in empty state for when the conversation hasn't started yet. We've used this pattern in a bunch of chat apps—it just works how users expect.

### Conversation component preview

<AIPreview path="conversation" />

## Installation

<Installer packageName="conversation" />

## More React AI components

Explore other AI components for Next.js chat interfaces:

<Cards>
  <Card
    href="/ai/message"
    title="React AI Message"
    description="Chat message bubbles"
  />
  <Card
    href="/ai/prompt-input"
    title="React AI Prompt Input"
    description="Message input area"
  />
  <Card
    href="/ai/loader"
    title="React AI Loader"
    description="Loading spinner"
  />
  <Card
    href="/ai/suggestion"
    title="React AI Suggestion"
    description="Quick reply buttons"
  />
  <Card
    href="/ai/sources"
    title="React AI Sources"
    description="Citation sources"
  />
  <Card
    href="/ai/reasoning"
    title="React AI Reasoning"
    description="AI thinking display"
  />
</Cards>

## Conversation component FAQ

<Accordions type="single">
  <Accordion id="conversation-scroll" title="How does auto-scroll work?">
    It uses use-stick-to-bottom, which is smart about when to scroll. New content triggers auto-scroll, but if the user manually scrolls up, it backs off and lets them read. Smooth animations on load and resize too.
  </Accordion>

  <Accordion id="conversation-button" title="When does the scroll button appear?">
    Only when you're not at the bottom. Click it and you smoothly scroll back to the latest message. Position it wherever you want with className.
  </Accordion>

  <Accordion id="conversation-empty" title="How do I show an empty state?">
    ConversationEmptyState takes title, description, and an optional icon. It centers itself in the conversation area. Or pass children if you want something completely custom.
  </Accordion>

  <Accordion id="conversation-accessibility" title="Is the conversation accessible?">
    Yep, the container has role=log so screen readers understand it's a conversation. The scroll button is properly labeled. Just make sure your messages have good ARIA attributes too.
  </Accordion>

</Accordions>