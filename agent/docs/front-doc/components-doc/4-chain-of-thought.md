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

## Code example
"use client";

import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtHeader,
  ChainOfThoughtImage,
  ChainOfThoughtSearchResult,
  ChainOfThoughtSearchResults,
  ChainOfThoughtStep,
} from "@/components/ai/chain-of-thought";
import { Image } from "@/components/ai/image";
import { ImageIcon, SearchIcon } from "lucide-react";

const exampleImage = {
  base64:
    "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",
  mimeType: "image/png",
};

const ChainOfThoughtExample = () => (
  <ChainOfThought defaultOpen>
    <ChainOfThoughtHeader />
    <ChainOfThoughtContent>
      <ChainOfThoughtStep
        icon={SearchIcon}
        label="Searching for chocolate chip cookie recipes"
        status="complete"
      >
        <ChainOfThoughtSearchResults>
          {[
            "https://www.allrecipes.com",
            "https://www.foodnetwork.com",
            "https://www.seriouseats.com",
          ].map((website) => (
            <ChainOfThoughtSearchResult key={website}>
              {new URL(website).hostname}
            </ChainOfThoughtSearchResult>
          ))}
        </ChainOfThoughtSearchResults>
      </ChainOfThoughtStep>

      <ChainOfThoughtStep
        icon={ImageIcon}
        label="Found a highly-rated recipe with 4.8 stars"
        status="complete"
      >
        <ChainOfThoughtImage caption="Classic chocolate chip cookies fresh from the oven.">
          <Image
            base64={exampleImage.base64}
            alt="Chocolate chip cookies"
            className="aspect-square h-[150px] border"
          />
        </ChainOfThoughtImage>
      </ChainOfThoughtStep>

      <ChainOfThoughtStep
        label="This recipe uses brown butter for extra flavor and requires chilling the dough for 24-36 hours. The cookies are crispy on the edges and chewy in the center."
        status="complete"
      />

      <ChainOfThoughtStep
        icon={SearchIcon}
        label="Looking for ingredient substitutions..."
        status="active"
      >
        <ChainOfThoughtSearchResults>
          {["https://www.kingarthurbaking.com", "https://www.thekitchn.com"].map(
            (website) => (
              <ChainOfThoughtSearchResult key={website}>
                {new URL(website).hostname}
              </ChainOfThoughtSearchResult>
            )
          )}
        </ChainOfThoughtSearchResults>
      </ChainOfThoughtStep>
    </ChainOfThoughtContent>
  </ChainOfThought>
);

export default ChainOfThoughtExample;
