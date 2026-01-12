# React AI Chain Of Thought
URL: /ai/chain-of-thought
React AI chain of thought component with collapsible reasoning steps and search results for transparent AI thinking

Ever noticed how some AI apps show you the thinking process—like "searching the web", "analyzing results", "forming response"? That's what this component does. It's a collapsible panel that breaks down the AI's reasoning into visible steps, so users aren't just staring at a spinner wondering what's happening. Each step can have its own status (complete, active, pending), custom icons, and even nested content like search results or images. Super useful for research assistants, agents that browse the web, or anywhere you want to build trust by showing your work. The whole thing collapses down to a single line when users don't care about the details. Built on Radix primitives so the animations and accessibility are solid out of the box.

### Chain Of Thought component preview

<AIPreview path="chain-of-thought" />

## Installation

<Installer packageName="chain-of-thought" />

## More React AI components

Explore other AI components for Next.js chat interfaces:

<Cards>
  <Card
    href="/ai/reasoning"
    title="React AI Reasoning"
    description="Simpler thinking display"
  />
  <Card
    href="/ai/message"
    title="React AI Message"
    description="Chat message container"
  />
  <Card
    href="/ai/tool"
    title="React AI Tool"
    description="Tool execution display"
  />
  <Card
    href="/ai/sources"
    title="React AI Sources"
    description="Citation sources list"
  />
  <Card
    href="/ai/task"
    title="React AI Task"
    description="Task progress tracking"
  />
  <Card
    href="/ai/plan"
    title="React AI Plan"
    description="Multi-step planning"
  />
</Cards>

## Chain Of Thought component FAQ

<Accordions type="single">
  <Accordion id="cot-controlled" title="How do I control the open/closed state?">
    You've got two options. For controlled mode, pass open and onOpenChange props and manage state yourself. For uncontrolled, just use defaultOpen and let the component handle it. Uses Radix's useControllableState under the hood, so it's flexible.
  </Accordion>

  <Accordion id="cot-steps" title="How do I show multiple reasoning steps?">
    Stack ChainOfThoughtStep components inside ChainOfThoughtContent. Each step takes a label, optional description, icon, and status (complete, active, or pending). They'll render in order with nice connecting lines between them.
  </Accordion>

  <Accordion id="cot-search" title="How do I display search results in the chain?">
    Nest a ChainOfThoughtSearchResults inside your step, then add ChainOfThoughtSearchResult badges for each result. Perfect for showing which URLs the AI searched or which documents it pulled from.
  </Accordion>

  <Accordion id="cot-animation" title="Are the transitions animated?">
    Yeah, everything animates smoothly. Steps fade and slide in as they appear, the collapsible uses Radix's built-in animations, and status changes transition nicely. All done with Tailwind's animate-in utilities.
  </Accordion>

</Accordions>