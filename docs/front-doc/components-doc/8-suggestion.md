# React AI Suggestion
URL: /ai/suggestion
React AI suggestion component with horizontally scrolling quick reply buttons for chat interfaces

Those pill-shaped "quick reply" buttons you see in chatbots? This is how you build them. You get a horizontal scroll area that hides the scrollbar (cleaner look), and each suggestion is a clickable button that passes its text to your handler. Click one, and it either fills the input or submits directly—your call. We put these above or below the input to help users get started or pick common follow-ups. Great for onboarding flows where users might not know what to ask, or for speeding up repetitive interactions.

### Suggestion component preview

<AIPreview path="suggestion" />

## Installation

<Installer packageName="suggestion" />

## More React AI components

Explore other AI components for Next.js chat interfaces:

<Cards>
  <Card
    href="/ai/prompt-input"
    title="React AI Prompt Input"
    description="Message input area"
  />
  <Card
    href="/ai/conversation"
    title="React AI Conversation"
    description="Chat container"
  />
  <Card
    href="/ai/message"
    title="React AI Message"
    description="Chat message bubbles"
  />
  <Card
    href="/ai/open-in-chat"
    title="React AI Open In Chat"
    description="External chat links"
  />
  <Card
    href="/ai/toolbar"
    title="React AI Toolbar"
    description="Action toolbar"
  />
  <Card
    href="/ai/loader"
    title="React AI Loader"
    description="Loading indicator"
  />
</Cards>

## Suggestion component FAQ

<Accordions type="single">
  <Accordion id="suggestion-click" title="How do I handle suggestion clicks?">
    Pass onClick to Suggestion—it receives the suggestion string as the argument. Wire it to setState for your input, or call your submit function directly if you want instant send.
  </Accordion>

  <Accordion id="suggestion-scroll" title="How does horizontal scrolling work?">
    Suggestions uses ScrollArea with horizontal orientation. The scrollbar's hidden for a cleaner look, but users can still scroll with touch, trackpad, or arrow keys. Works great on mobile.
  </Accordion>

  <Accordion id="suggestion-styling" title="Can I customize button appearance?">
    It's just a Button under the hood, so you get all the usual props. Default is outline variant with rounded-full. Change variant, size, or className to match your design system.
  </Accordion>

  <Accordion id="suggestion-content" title="How do I show different text than the suggestion?">
    Pass children for custom display text. The onClick callback still gets the suggestion prop value, so you can show 'Tell me more' but actually send 'Please provide more details about the previous topic'.
  </Accordion>

</Accordions>