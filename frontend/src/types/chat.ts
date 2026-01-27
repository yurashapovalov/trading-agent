// Chat types

export type ChatItem = {
  id: string
  title: string
}

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

export type Feedback = {
  positive_feedback?: string
  negative_feedback?: string
}

export type ChatMessage = {
  role: "user" | "assistant"
  content: string
  preview?: string              // Expert context before data (from responder)
  request_id?: string
  tools_used?: ToolUsage[]
  agent_steps?: AgentStep[]
  route?: string
  validation_passed?: boolean
  usage?: Usage
  feedback?: Feedback
  data_card?: DataCard
  offer_analysis?: boolean
}

// Data card info from backend
export type DataCard = {
  title: string
  row_count: number
  request_id?: string  // For loading full data from API
}

// SSE event types from backend
export type SSEEvent =
  | { type: "step_start"; agent: string; message: string }
  | { type: "step_end"; agent: string; result?: Record<string, unknown>; duration_ms?: number; output?: Record<string, unknown> }
  | { type: "tool_call"; tool: string; args: Record<string, unknown> }
  | { type: "sql_executed"; query: string; rows_found: number; error?: string; duration_ms: number }
  | { type: "validation"; status: "ok" | "rewrite" | "failed" }
  | { type: "tool_start"; name: string; input: Record<string, unknown> }
  | { type: "tool_end"; name: string; input: Record<string, unknown>; result: unknown; duration_ms: number }
  | { type: "text_delta"; content: string }
  | { type: "suggestions"; suggestions: string[] }
  | { type: "data_title"; title: string }
  | { type: "data_ready"; row_count: number; data: Record<string, unknown> }
  | { type: "offer_analysis"; message: string }
  | { type: "usage"; input_tokens: number; output_tokens: number; thinking_tokens?: number; cost: number }
  | { type: "chat_id"; chat_id: string }
  | { type: "chat_title"; chat_id: string; title: string }
  | { type: "done"; request_id?: string }
  | { type: "error"; message: string }
  | { type: "acknowledge"; content: string }
  | { type: "data_card"; title: string; row_count: number }
