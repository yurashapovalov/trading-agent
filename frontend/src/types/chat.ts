// Chat message types

export type ToolUsage = {
  name: string
  input: Record<string, unknown>
  result?: unknown
  duration_ms?: number
  status: "running" | "completed"
}

export type AgentStep = {
  agent: string
  message: string
  status: "running" | "completed"
  result?: Record<string, unknown>
  tools?: ToolUsage[]
  durationMs?: number
}

export type Usage = {
  input_tokens: number
  output_tokens: number
  thinking_tokens?: number
  cost: number
}

export type ChatMessage = {
  role: "user" | "assistant"
  content: string
  tools_used?: ToolUsage[]
  agent_steps?: AgentStep[]
  route?: string
  validation_passed?: boolean
  usage?: Usage
}

// SSE event types from backend
export type SSEEvent =
  | { type: "step_start"; agent: string; message: string }
  | { type: "step_end"; agent: string; result?: Record<string, unknown>; duration_ms?: number }
  | { type: "tool_call"; tool: string; args: Record<string, unknown> }
  | { type: "sql_executed"; query: string; rows_found: number; error?: string; duration_ms: number }
  | { type: "validation"; status: "ok" | "rewrite" | "failed" }
  | { type: "tool_start"; name: string; input: Record<string, unknown> }
  | { type: "tool_end"; name: string; input: Record<string, unknown>; result: unknown; duration_ms: number }
  | { type: "text_delta"; content: string }
  | { type: "suggestions"; suggestions: string[] }
  | { type: "usage"; input_tokens: number; output_tokens: number; thinking_tokens?: number; cost: number }
  | { type: "chat_id"; chat_id: string }
  | { type: "done" }
  | { type: "error"; message: string }
