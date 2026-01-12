# React AI Artifact
URL: /ai/artifact
React AI artifact component for displaying code, documents, and generated content with action buttons like Claude Artifacts

You know that panel Claude uses to show generated code or documents? This component lets you build exactly that. It's a composable artifact viewer where you can display pretty much anything your AI generates—code snippets, markdown docs, SVGs, HTML previews, you name it. The API is straightforward: wrap everything in Artifact, add an ArtifactHeader with your title, throw in some ArtifactActions for copy/download buttons, and dump your content into ArtifactContent. It handles all the boring stuff like scroll overflow, close buttons, and tooltips. Built on shadcn/ui so it just works with your existing setup. We use it for code generation previews, document viewers, and basically anywhere we need to show AI output separately from the chat. Plays nice with Vercel AI SDK streaming too—just update the content as tokens come in.

### Artifact component preview

<AIPreview path="artifact" />

## Installation

<Installer packageName="artifact" />

## More React AI components

Explore other AI components for Next.js chat interfaces:

<Cards>
  <Card
    href="/ai/code-block"
    title="React AI Code Block"
    description="Syntax highlighted code display"
  />
  <Card
    href="/ai/panel"
    title="React AI Panel"
    description="Resizable side panel"
  />
  <Card
    href="/ai/message"
    title="React AI Message"
    description="Chat message bubbles"
  />
  <Card
    href="/ai/tool"
    title="React AI Tool"
    description="Tool execution display"
  />
  <Card
    href="/ai/reasoning"
    title="React AI Reasoning"
    description="Thinking process display"
  />
  <Card
    href="/ai/canvas"
    title="React AI Canvas"
    description="Visual node canvas"
  />
</Cards>

## Artifact component FAQ

<Accordions type="single">
  <Accordion id="artifact-types" title="What types of artifacts can I display?">
    Honestly, anything. Code with syntax highlighting, markdown documents, SVGs, HTML previews, rendered React components, charts—whatever you throw at it. ArtifactContent is just a scrollable container that takes any React children, so go wild.
  </Accordion>

  <Accordion id="artifact-actions" title="How do I add custom action buttons?">
    Drop an ArtifactAction inside ArtifactActions in the header. Give it an icon prop (lucide-react icons work great) and a tooltip string. Wire up your onClick for copy, download, whatever you need. Dead simple.
  </Accordion>

  <Accordion id="artifact-close" title="How does the close button work?">
    ArtifactClose gives you an X button out of the box. Just pass an onClick to toggle your visibility state. Works with useState, Zustand, Redux—however you manage state.
  </Accordion>

  <Accordion id="artifact-styling" title="Can I customize the artifact appearance?">
    Every subcomponent takes a className prop, so you can override anything with Tailwind. The defaults give you a nice bordered card with subtle shadow, but make it yours.
  </Accordion>

  <Accordion id="artifact-streaming" title="Does it work with streaming responses?">
    Yep, works great with Vercel AI SDK. Just update the ArtifactContent children as tokens stream in. You get that nice real-time generation feel, just like Claude.
  </Accordion>

</Accordions>
