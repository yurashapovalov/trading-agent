# React AI Message
URL: /ai/message
React AI message component with user/assistant styling, branching, attachments, and streaming markdown for chat interfaces

This is the big one—the message component that handles everything in a chat UI. User messages, assistant messages, file attachments, image previews, conversation branching (like when you regenerate a response and want to flip between versions), streaming markdown, action buttons for copy/like/retry. It's a lot, but it's all composable so you pick what you need. User messages go right with a subtle background, assistant messages go left and render markdown. The markdown rendering uses Streamdown which is optimized for streaming—no weird flashing as tokens come in. We've battle-tested this on production chat apps with thousands of messages. It handles the edge cases.

### Message component preview

<AIPreview path="message" />

## Installation

<Installer packageName="message" />

## More React AI components

Explore other AI components for Next.js chat interfaces:

<Cards>
  <Card
    href="/ai/conversation"
    title="React AI Conversation"
    description="Chat container with scroll"
  />
  <Card
    href="/ai/prompt-input"
    title="React AI Prompt Input"
    description="Message input area"
  />
  <Card
    href="/ai/reasoning"
    title="React AI Reasoning"
    description="AI thinking display"
  />
  <Card
    href="/ai/sources"
    title="React AI Sources"
    description="Citation sources"
  />
  <Card
    href="/ai/tool"
    title="React AI Tool"
    description="Tool execution display"
  />
  <Card
    href="/ai/loader"
    title="React AI Loader"
    description="Loading spinner"
  />
</Cards>

## Message component FAQ

<Accordions type="single">
  <Accordion id="message-roles" title="How do user and assistant messages differ?">
    Set the from prop to user or assistant. User messages align right with a secondary background. Assistant messages align left, no background, just the content. All the styling is handled for you.
  </Accordion>

  <Accordion id="message-branching" title="How does conversation branching work?">
    Wrap your message alternatives in MessageBranch with MessageBranchContent. Add a MessageBranchSelector with Previous/Next/Page buttons to navigate between versions. The context keeps track of which branch you're on.
  </Accordion>

  <Accordion id="message-streaming" title="How do I render streaming markdown?">
    MessageResponse wraps Streamdown, which is built for streaming. Just pass your markdown string as children. It's memoized so you don't get re-render hell while tokens are coming in.
  </Accordion>

  <Accordion id="message-attachments" title="How do I show file attachments?">
    MessageAttachments container with MessageAttachment items inside. Pass the FileUIPart from AI SDK. Images get previews, other files show an icon. Add onRemove if you want a delete button.
  </Accordion>

</Accordions>