# React AI Sources
URL: /ai/sources
React AI sources component with collapsible list of citation links for RAG and research applications

If you're building a RAG-powered chat or research assistant, you need a way to show where information came from. This component gives you a collapsible "Used X sources" section that expands to reveal citation links. Click the trigger, see the sources—simple as that. Each source renders with a book icon and opens in a new tab. The whole thing stays collapsed by default so it doesn't clutter up long responses, but the info's there when users want to verify or dig deeper. Essential for any AI that retrieves documents and needs to show its work.

### Sources component preview

<AIPreview path="sources" />

## Installation

<Installer packageName="sources" />

## More React AI components

Explore other AI components for Next.js chat interfaces:

<Cards>
  <Card
    href="/ai/inline-citation"
    title="React AI Inline Citation"
    description="Inline source badges"
  />
  <Card
    href="/ai/message"
    title="React AI Message"
    description="Chat message bubbles"
  />
  <Card
    href="/ai/chain-of-thought"
    title="React AI Chain Of Thought"
    description="Reasoning with sources"
  />
  <Card
    href="/ai/reasoning"
    title="React AI Reasoning"
    description="AI thinking display"
  />
  <Card
    href="/ai/web-preview"
    title="React AI Web Preview"
    description="URL preview cards"
  />
  <Card
    href="/ai/tool"
    title="React AI Tool"
    description="Tool execution display"
  />
</Cards>

## Sources component FAQ

<Accordions type="single">
  <Accordion id="sources-count" title="How do I show the source count?">
    Pass count to SourcesTrigger and it shows 'Used X sources' automatically. If you want custom text like 'Referenced 5 documents', just pass children to override the default.
  </Accordion>

  <Accordion id="sources-links" title="How do I render source links?">
    Drop Source components inside SourcesContent with href and title. Each one gets a book icon and opens in a new tab (with noreferrer for security). You can pass children for completely custom rendering if the default doesn't fit.
  </Accordion>

  <Accordion id="sources-animation" title="Are the transitions animated?">
    Yep, there's a slide and fade animation when expanding/collapsing. Uses Tailwind's animate-in/out with data-state selectors. Feels smooth without being distracting.
  </Accordion>

  <Accordion id="sources-styling" title="Can I customize the appearance?">
    Everything takes className. The default uses your primary color for text, but you can override colors, spacing, icons—whatever you need to match your design.
  </Accordion>

</Accordions>