# React AI Queue
URL: /ai/queue
React AI queue component with collapsible sections showing pending messages and todo items for agent workflows

For agentic AI that handles multiple tasks or queued messages, you need a way to show what's pending. This component gives you collapsible sections—one for queued messages, one for todos, whatever you need. Each section has a count badge so users can see at a glance how much is waiting. Items can have status indicators, descriptions, even file attachments with image previews. When the list gets long, it scrolls nicely. We built this for agent UIs where the AI is working through a backlog of tasks and users want visibility into what's coming up. Keeps things organized without overwhelming the interface.

### Queue component preview

<AIPreview path="queue" />

## Installation

<Installer packageName="queue" />

## More React AI components

Explore other AI components for Next.js chat interfaces:

<Cards>
  <Card
    href="/ai/task"
    title="React AI Task"
    description="Individual task display"
  />
  <Card
    href="/ai/plan"
    title="React AI Plan"
    description="Task planning card"
  />
  <Card
    href="/ai/message"
    title="React AI Message"
    description="Chat message bubbles"
  />
  <Card
    href="/ai/conversation"
    title="React AI Conversation"
    description="Chat container"
  />
  <Card
    href="/ai/prompt-input"
    title="React AI Prompt Input"
    description="Message input"
  />
  <Card
    href="/ai/toolbar"
    title="React AI Toolbar"
    description="Action toolbar"
  />
</Cards>

## Queue component FAQ

<Accordions type="single">
  <Accordion id="queue-sections" title="How do I organize queue items?">
    QueueSection wraps each group. Inside that, QueueSectionTrigger for the header (with QueueSectionLabel showing count) and QueueSectionContent for the items. They collapse by default—use defaultOpen if you want them expanded.
  </Accordion>

  <Accordion id="queue-items" title="What item types are supported?">
    QueueItem is your container. Add QueueItemIndicator for the status dot, QueueItemContent for the main text, QueueItemDescription for secondary info. Pass completed to strike things through.
  </Accordion>

  <Accordion id="queue-attachments" title="How do I show attachments?">
    QueueItemAttachment wraps your files. Use QueueItemImage for image thumbnails or QueueItemFile for other files (shows a paperclip icon with the filename).
  </Accordion>

  <Accordion id="queue-scrolling" title="How does the scroll area work?">
    QueueList uses a ScrollArea that maxes out at a reasonable height. When you have more items than fit, you get a nice scrollbar. Padding is handled so nothing gets clipped.
  </Accordion>

</Accordions>