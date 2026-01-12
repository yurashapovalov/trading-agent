# React AI Task
URL: /ai/task
React AI task component with collapsible search-style display for showing AI operation progress

When your AI is doing work—searching docs, processing files, running queries—users want to know what's happening. This component shows that activity in a collapsible block with a search icon and title. Click to expand and see the details: which files were touched, what results came back, what's being processed. The left border accent gives it that "activity log" feel. Starts expanded by default so users see results immediately, but collapses nicely when they want to move on. Think of it as a mini activity feed for individual AI operations.

### Task component preview

<AIPreview path="task" />

## Installation

<Installer packageName="task" />

## More React AI components

Explore other AI components for Next.js chat interfaces:

<Cards>
  <Card
    href="/ai/plan"
    title="React AI Plan"
    description="Multi-task planning"
  />
  <Card
    href="/ai/queue"
    title="React AI Queue"
    description="Task queue display"
  />
  <Card
    href="/ai/tool"
    title="React AI Tool"
    description="Tool execution display"
  />
  <Card
    href="/ai/chain-of-thought"
    title="React AI Chain Of Thought"
    description="Reasoning steps"
  />
  <Card
    href="/ai/reasoning"
    title="React AI Reasoning"
    description="AI thinking display"
  />
  <Card
    href="/ai/message"
    title="React AI Message"
    description="Chat message bubbles"
  />
</Cards>

## Task component FAQ

<Accordions type="single">
  <Accordion id="task-trigger" title="How do I customize the task trigger?">
    TaskTrigger takes a title prop for the label. Default gives you a search icon and chevron. If you need something totally different, pass children to override the whole thing.
  </Accordion>

  <Accordion id="task-content" title="What goes inside TaskContent?">
    The content area has that left border accent. Drop TaskItem components for individual results, TaskItemFile for file badges. Everything animates smoothly on expand.
  </Accordion>

  <Accordion id="task-default" title="Should tasks start open or closed?">
    Defaults to open so users see results right away. Set defaultOpen=false if you want collapsed. For programmatic control, use open and onOpenChange props.
  </Accordion>

  <Accordion id="task-files" title="How do I show file references?">
    TaskItemFile gives you those nice inline badges—bordered pill with the filename. Perfect for showing 'Searched config.json', 'Found in utils.ts', that kind of thing.
  </Accordion>

</Accordions>

## Code

"use client";

import { SiReact } from "@icons-pack/react-simple-icons";
import {
  Task,
  TaskContent,
  TaskItem,
  TaskItemFile,
  TaskTrigger,
} from "@/components/ai/task";
import { nanoid } from "nanoid";
import type { ReactNode } from "react";

const Example = () => {
  const tasks: { key: string; value: ReactNode }[] = [
    { key: nanoid(), value: 'Searching "app/page.tsx, components structure"' },
    {
      key: nanoid(),
      value: (
        <span className="inline-flex items-center gap-1" key="read-page-tsx">
          Read
          <TaskItemFile>
            <SiReact className="size-4" color="#149ECA" />
            <span>page.tsx</span>
          </TaskItemFile>
        </span>
      ),
    },
    { key: nanoid(), value: "Scanning 52 files" },
    { key: nanoid(), value: "Scanning 2 files" },
    {
      key: nanoid(),
      value: (
        <span className="inline-flex items-center gap-1" key="read-layout-tsx">
          Reading files
          <TaskItemFile>
            <SiReact className="size-4" color="#149ECA" />
            <span>layout.tsx</span>
          </TaskItemFile>
        </span>
      ),
    },
  ];

  return (
    <div style={{ height: "200px" }}>
      <Task className="w-full">
        <TaskTrigger title="Found project files" />
        <TaskContent>
          {tasks.map((task) => (
            <TaskItem key={task.key}>{task.value}</TaskItem>
          ))}
        </TaskContent>
      </Task>
    </div>
  );
};

export default Example;
