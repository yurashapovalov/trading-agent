# React AI Prompt Input
URL: /ai/prompt-input
React AI prompt input component with textarea, file attachments, speech-to-text, and customizable actions for chat interfaces

The input box is where users spend most of their time in a chat app, so it needs to be good. This one does everything—auto-resizing textarea that grows with content, drag-and-drop file attachments with previews, paste support for images, speech-to-text if you want it, action buttons, dropdowns, even a command palette if you're feeling fancy. It's composable so you pick what you need. The textarea handles Enter to submit, Shift+Enter for newlines, all the keyboard stuff users expect. There's a provider pattern if you need to access the input state from outside (like clearing after send). We've iterated on this across multiple chat apps—it handles the edge cases you don't think about until you ship.

### Prompt Input component preview

<AIPreview path="prompt-input" />

## Installation

<Installer packageName="prompt-input" />

## More React AI components

Explore other AI components for Next.js chat interfaces:

<Cards>
  <Card
    href="/ai/conversation"
    title="React AI Conversation"
    description="Chat container with scroll"
  />
  <Card
    href="/ai/message"
    title="React AI Message"
    description="Chat message bubbles"
  />
  <Card
    href="/ai/suggestion"
    title="React AI Suggestion"
    description="Quick reply buttons"
  />
  <Card
    href="/ai/model-selector"
    title="React AI Model Selector"
    description="Model switching"
  />
  <Card
    href="/ai/context"
    title="React AI Context"
    description="Token usage display"
  />
  <Card
    href="/ai/toolbar"
    title="React AI Toolbar"
    description="Action toolbar"
  />
</Cards>

## Prompt Input component FAQ

<Accordions type="single">
  <Accordion id="prompt-attachments" title="How do file attachments work?">
    PromptInputAttachments shows the attached files. The main component handles drag-drop and paste automatically. On submit, files become data URLs. You can set accept, maxFiles, maxFileSize to control what's allowed.
  </Accordion>

  <Accordion id="prompt-provider" title="When should I use PromptInputProvider?">
    When you need to touch the input state from outside—like clearing the input after a successful send, or reading attachments from a parent. Otherwise the component manages its own state and you don't need the provider.
  </Accordion>

  <Accordion id="prompt-speech" title="How does speech-to-text work?">
    PromptInputSpeechButton hooks into the Web Speech API. Pass it a textareaRef and it appends transcribed text. There's an animated state while listening. Obviously needs browser support and mic permissions.
  </Accordion>

  <Accordion id="prompt-submit" title="How do I handle form submission?">
    onSubmit gets called with an object containing text and files. Files are FileUIPart arrays with data URLs ready to send. Return a promise and it'll show a loading state. Attachments auto-clear on success.
  </Accordion>

</Accordions>