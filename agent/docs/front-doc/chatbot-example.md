# React AI Chatbot
URL: /ai/chatbot
Complete ChatGPT-style chatbot interface with streaming responses, reasoning display, model selection, sources, and message branching for React and Next.js

A complete chatbot interface that combines all the AI components into a production-ready chat experience. This example shows how to build a ChatGPT-style interface with streaming responses, reasoning/thinking blocks, source citations, model selection, suggestion pills, and message branching for regenerated responses.

<AIPreview path="chatbot" />

## What's included

This example demonstrates:

- **Conversation container** with auto-scroll and scroll-to-bottom button
- **Message bubbles** with user/assistant styling and markdown rendering
- **Streaming responses** with word-by-word typing effect
- **Reasoning blocks** that show AI thinking process (collapsible)
- **Source citations** with expandable link list
- **Model selector** dropdown with provider logos
- **Suggestion pills** for quick prompts
- **Message branching** to navigate between regenerated responses
- **Prompt input** with attachments, microphone, and web search toggles

## Components used

This example uses the following AI components:

<Cards>
  <Card
    href="/ai/conversation"
    title="Conversation"
    description="Chat container with scroll"
  />
  <Card
    href="/ai/message"
    title="Message"
    description="Message bubbles with branching"
  />
  <Card
    href="/ai/prompt-input"
    title="Prompt Input"
    description="Input with attachments"
  />
  <Card
    href="/ai/model-selector"
    title="Model Selector"
    description="Model picker dropdown"
  />
  <Card
    href="/ai/reasoning"
    title="Reasoning"
    description="Thinking display"
  />
  <Card
    href="/ai/sources"
    title="Sources"
    description="Citation links"
  />
</Cards>

## FAQ

<Accordions type="single">
  <Accordion id="chatbot-streaming" title="How does streaming work?">
    The example simulates streaming by adding words progressively. In production, you'd use Vercel AI SDK's useChat hook which handles the streaming protocol. The MessageResponse component renders markdown as it streams in.
  </Accordion>

  <Accordion id="chatbot-branching" title="What's the message branching for?">
    When users regenerate a response, you store multiple versions. MessageBranch lets them flip between versions with Previous/Next buttons. Shows "1 of 3" so they know how many alternatives exist.
  </Accordion>

  <Accordion id="chatbot-backend" title="How do I connect this to a real AI?">
    Replace the mock addUserMessage logic with Vercel AI SDK's useChat or useCompletion. The UI components don't care where the data comes from—they just render whatever messages you pass.
  </Accordion>

  <Accordion id="chatbot-customization" title="Can I remove features I don't need?">
    Absolutely. Don't need model selection? Remove ModelSelector. No reasoning? Skip the Reasoning component. No sources? Leave them out. Each piece is independent.
  </Accordion>

</Accordions>