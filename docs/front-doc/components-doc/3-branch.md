# React AI Branch
URL: /ai/branch
React AI branch component with message versioning and navigation for chat regeneration workflows

Ever regenerate an AI response and want to flip between versions? That's what Branch does. When users hit "regenerate," you don't have to throw away the old response—store both and let them navigate with Previous/Next buttons. Shows "1 of 3" so they know how many versions exist. The selector only appears when there's more than one branch, so it stays hidden for normal single-response messages. Wraps around your existing Message components without changing their structure. Great for chat apps where users might want to compare different AI responses or go back to an earlier version.

### Branch component preview

<AIPreview path="branch" />

## Installation

<Installer packageName="branch" />

## More React AI components

Explore other AI components for Next.js chat interfaces:

<Cards>
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
    href="/ai/reasoning"
    title="React AI Reasoning"
    description="AI thinking display"
  />
  <Card
    href="/ai/suggestion"
    title="React AI Suggestion"
    description="Quick reply buttons"
  />
  <Card
    href="/ai/prompt-input"
    title="React AI Prompt Input"
    description="Message input area"
  />
  <Card
    href="/ai/toolbar"
    title="React AI Toolbar"
    description="Action toolbar"
  />
</Cards>

## Branch component FAQ

<Accordions type="single">
  <Accordion id="branch-setup" title="How do I set up branching?">
    Wrap your messages in Branch, put the different versions inside BranchMessages as children, add BranchSelector with the nav buttons. Each child of BranchMessages is a branch that users can flip through.
  </Accordion>

  <Accordion id="branch-navigation" title="How do users switch between branches?">
    BranchPrevious and BranchNext buttons. They cycle through—going past the end loops back to the start. Keyboard support would need custom implementation.
  </Accordion>

  <Accordion id="branch-visibility" title="When does the selector show?">
    Only when there's more than one branch. Single messages don't show any UI. Once you regenerate and have 2+ versions, the selector appears automatically.
  </Accordion>

  <Accordion id="branch-callback" title="How do I track which branch is active?">
    onBranchChange callback on Branch fires whenever users navigate. You get the index. Useful for analytics or syncing with your state management.
  </Accordion>

</Accordions>