# React Components for Conversational AI

Open-source React components for building ChatGPT-style AI chat interfaces. Production-ready UI with TypeScript, Vercel AI SDK support, streaming responses, tool calls, and shadcn/ui design.

You've seen how ChatGPT, Claude, and Gemini handle conversations. The streaming text. The collapsible reasoning. The tool call displays. The message branching when you regenerate. Now you need to build the same thing.

The problem? Generic React UI libraries weren't designed for AI. You end up writing custom components for every AI-specific pattern—streaming markdown, tool execution displays, reasoning blocks, citation lists. Then you maintain all of it.

These components solve that. 25+ purpose-built React components for conversational AI interfaces. They integrate with the Vercel AI SDK, follow shadcn/ui's copy-paste philosophy, and handle every pattern you've seen in production AI apps.

## The Problem with Building AI Interfaces

When you start building a ChatGPT-style app with standard React components, you quickly hit walls:

**Streaming responses** — Regular text components don't handle markdown that renders character by character without flickering. You need a component that buffers, parses, and renders streaming content smoothly.

**Tool calls** — The AI SDK gives you `tool-call` and `tool-result` parts, but you need UI that shows what function is running, what inputs it received, and what it returned. With loading states. And error handling.

**Reasoning/thinking** — Models like Claude and o1 emit thinking tokens. You need collapsible blocks that show "Thought for 12 seconds" and expand to reveal the reasoning. That auto-collapse when streaming finishes.

**Message branching** — When users regenerate a response, you store multiple versions. Now you need UI to navigate between them: "2 of 3" with Previous/Next buttons.

**Citations** — Grounded responses include source links. You need expandable citation lists that don't clutter the message but are accessible when needed.

Each of these is a custom implementation with standard libraries. With these components, they're one import away.

## Why shadcn/ui for AI Components?

The shadcn/ui approach works perfectly for AI interfaces:

**You own the code** — Every component copies into your project. When your designer says "make the reasoning block purple," you open the file and change it. No waiting for library updates. No fighting with CSS overrides.

**Composable architecture** — Mix and match components. Use `Message` without `Conversation`. Use `Tool` without the full chat interface. Each component is independent.

**Familiar patterns** — If you've used shadcn/ui, you already know how these work. Tailwind classes, Radix primitives, TypeScript props. Same development experience.

**AI SDK integration** — Components understand Vercel AI SDK data structures. Pass `message.parts` and they render text, tool calls, and reasoning automatically.

---

## Examples

Complete interfaces showing how components work together.

<Cards>
  <Card href="/ai/chatbot" title="AI Chatbot" description="Full ChatGPT-style interface with streaming, reasoning, model selection, and message branching" />
</Cards>

---

## Core Chat Components

The foundation of any conversational AI interface.

<Cards>
  <Card href="/ai/message" title="Message" description="Chat bubbles with user/assistant styling, attachments, and markdown" />
  <Card href="/ai/conversation" title="Conversation" description="Auto-scrolling container with scroll-to-bottom button" />
  <Card href="/ai/prompt-input" title="Prompt Input" description="Auto-resizing textarea with file attachments, toolbar, and submit handling" />
  <Card href="/ai/model-selector" title="Model Selector" description="Searchable dropdown with provider logos and keyboard navigation" />
  <Card href="/ai/suggestion" title="Suggestion" description="Scrollable suggestion pills for quick prompts" />
  <Card href="/ai/actions" title="Actions" description="Icon button toolbar for copy, regenerate, thumbs up/down" />
</Cards>

---

## AI Response Components

Handle the patterns unique to AI—tool calls, reasoning, citations, and response variations.

<Cards>
  <Card href="/ai/reasoning" title="Reasoning" description="Collapsible thinking blocks with duration and auto-collapse" />
  <Card href="/ai/tool" title="Tool" description="Function call displays with inputs, outputs, and status indicators" />
  <Card href="/ai/sources" title="Sources" description="Expandable citation lists for grounded responses" />
  <Card href="/ai/branch" title="Branch" description="Navigate between regenerated response versions" />
  <Card href="/ai/chain-of-thought" title="Chain of Thought" description="Step-by-step reasoning with expandable details" />
  <Card href="/ai/inline-citation" title="Inline Citation" description="Numbered citations within response text" />
</Cards>

---

## Loading & Progress

Visual feedback for streaming, background operations, and multi-step tasks.

<Cards>
  <Card href="/ai/loader" title="Loader" description="Animated loading indicators in multiple sizes" />
  <Card href="/ai/shimmer" title="Shimmer" description="Skeleton loading that pulses while content streams" />
  <Card href="/ai/task" title="Task" description="Task lists with file references and completion states" />
  <Card href="/ai/queue" title="Queue" description="Multi-task queue with progress visualization" />
  <Card href="/ai/plan" title="Plan" description="Expandable plan display with step tracking" />
</Cards>

---

## Code & Content

Display code blocks, generated artifacts, and rich content.

<Cards>
  <Card href="/ai/code-block" title="Code Block" description="Syntax-highlighted code with copy button and language detection" />
  <Card href="/ai/artifact" title="Artifact" description="Expandable panels for generated files and content" />
  <Card href="/ai/image" title="Image" description="AI-generated images with loading states" />
  <Card href="/ai/web-preview" title="Web Preview" description="Iframe preview for generated HTML/websites" />
</Cards>

---

## User Interaction

Components for confirmations, context, and user decisions.

<Cards>
  <Card href="/ai/confirmation" title="Confirmation" description="Accept/reject dialogs for tool execution approval" />
  <Card href="/ai/context" title="Context" description="Display and manage conversation context" />
  <Card href="/ai/checkpoint" title="Checkpoint" description="Save and restore conversation states" />
  <Card href="/ai/open-in-chat" title="Open in Chat" description="Share and open content in chat interfaces" />
</Cards>

---

## How It Works with Vercel AI SDK

The AI SDK handles state management and streaming. These components handle rendering. They work together seamlessly.

```tsx
import { Message, MessageContent, MessageResponse } from "@/components/ai/message";
import { Conversation, ConversationContent } from "@/components/ai/conversation";
import { Tool } from "@/components/ai/tool";
import { Reasoning } from "@/components/ai/reasoning";
import { useChat } from "@ai-sdk/react";

export default function Chat() {
  const { messages } = useChat();

  return (
    <Conversation>
      <ConversationContent>
        {messages.map((message) => (
          <Message from={message.role} key={message.id}>
            <MessageContent>
              {message.parts?.map((part, i) => {
                if (part.type === "text")
                  return <MessageResponse key={i}>{part.text}</MessageResponse>;
                if (part.type === "tool-call")
                  return <Tool key={i} name={part.toolName} status="complete" />;
                if (part.type === "reasoning")
                  return <Reasoning key={i}>{part.reasoning}</Reasoning>;
              })}
            </MessageContent>
          </Message>
        ))}
      </ConversationContent>
    </Conversation>
  );
}
```

No manual stream parsing. No custom scroll handling. No reimplementing tool call displays. The SDK manages the AI, the components manage the UI.

---

## Frequently Asked Questions

<Accordions>
  <Accordion title="How do I install these components?">
    Use the shadcn CLI: `npx shadcn@latest add https://shadcn.io/r/message.json`. Components copy into `components/ai/` in your project. Install only what you need—they're independent.
  </Accordion>

  <Accordion title="Do these work with the Vercel AI SDK?">
    Yes, they're designed for it. Use `useChat` or `useCompletion` for state, render with these components. They understand AI SDK message structures, streaming, tool calls, and reasoning parts.
  </Accordion>

  <Accordion title="Can I use these without Vercel AI SDK?">
    Absolutely. The components just render props you pass them. Use any AI backend—OpenAI directly, Anthropic, local models. Just format your data to match the expected props.
  </Accordion>

  <Accordion title="Can I customize the styling?">
    Completely. The code lives in your project. Edit Tailwind classes, change structure, add features. These are your components now—no library updates needed, no CSS override battles.
  </Accordion>

  <Accordion title="What about streaming responses?">
    `MessageResponse` handles streaming markdown properly. Content renders as it arrives without layout shifts or flickering. It uses the `streamdown` library for optimized streaming markdown.
  </Accordion>

  <Accordion title="How do tool calls display?">
    The `Tool` component shows function name, inputs (collapsible JSON), outputs, and status (pending, running, complete, error). It handles both streaming and completed tool calls.
  </Accordion>

  <Accordion title="What's message branching?">
    When users regenerate responses, you store multiple versions. `Branch` provides Previous/Next navigation with "2 of 3" indicators. Users can flip between AI response variations.
  </Accordion>

  <Accordion title="Do I need all the components?">
    No. They're independent. A minimal chat needs `Message`, `Conversation`, and `PromptInput`. Add `Tool`, `Reasoning`, `Sources` as your AI features grow. Install only what you use.
  </Accordion>
</Accordions>