# Рефакторинг: AI Elements интеграция

## Цель
Показывать в UI какие инструменты использует агент во время работы.

## Архитектура

```
┌─────────────────┐     fetch      ┌─────────────────┐
│  Next.js + AI   │ ────────────►  │  Python FastAPI │
│    Elements     │ ◄────────────  │   + Claude API  │
│   (UI только)   │    JSON        │   (tool calls)  │
└─────────────────┘                └─────────────────┘
```

**Важно:** НЕ используем `useChat` из AI SDK - у нас свой Python backend.
Берём только UI компоненты из AI Elements.

## Компоненты AI Elements

Установка:
```bash
cd frontend
npx ai-elements@latest add tool
npx ai-elements@latest add message
npx ai-elements@latest add conversation
npx ai-elements@latest add loader
```

Компоненты:
- `<Conversation>` - контейнер с авто-скроллом
- `<Message>` - сообщение с markdown, actions
- `<Tool>` - collapsible показ tool call
- `<Loader>` - индикатор загрузки

## Изменения Backend

### 1. agent/llm.py

Изменить `chat()` чтобы возвращал структуру:

```python
def chat(self, user_message: str) -> dict:
    """
    Returns:
        {
            "response": str,
            "tools_used": [
                {
                    "name": "find_optimal_entries",
                    "input": {"symbol": "NQ", ...},
                    "result": {...},
                    "duration_ms": 123
                }
            ]
        }
    """
    tools_used = []

    # В цикле обработки tool calls:
    for tool_use in tool_uses:
        result = self.registry.execute(tool_use.name, tool_use.input)
        tools_used.append({
            "name": tool_use.name,
            "input": tool_use.input,
            "result": result,
            "duration_ms": ...
        })

    return {
        "response": text_response,
        "tools_used": tools_used
    }
```

### 2. api.py

```python
from typing import Any

class ToolUsage(BaseModel):
    name: str
    input: dict
    result: Any
    duration_ms: float

class ChatResponse(BaseModel):
    response: str
    session_id: str
    tools_used: list[ToolUsage] = []

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    agent = get_agent(request.session_id)
    result = agent.chat(request.message)  # теперь возвращает dict
    return ChatResponse(
        response=result["response"],
        session_id=request.session_id,
        tools_used=result.get("tools_used", [])
    )
```

## Изменения Frontend

### 1. Установить компоненты

```bash
cd frontend
npx ai-elements@latest add tool message conversation loader
```

### 2. page.tsx - полный код

```tsx
'use client'

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation'
import {
  Message,
  MessageContent,
  MessageResponse,
} from '@/components/ai-elements/message'
import {
  Tool,
  ToolContent,
  ToolTrigger,
} from '@/components/ai-elements/tool'
import { Loader } from '@/components/ai-elements/loader'
import {
  PromptInput,
  PromptInputAction,
  PromptInputActions,
  PromptInputTextarea,
} from '@/components/ui/prompt-input'
import { Button } from '@/components/ui/button'
import { ArrowUp, Square } from 'lucide-react'
import { useState } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type ToolUsage = {
  name: string
  input: Record<string, any>
  result: any
  duration_ms: number
}

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  tools_used?: ToolUsage[]
}

export default function Chat() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async () => {
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsLoading(true)

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage }),
      })

      const data = await response.json()
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: data.response,
          tools_used: data.tools_used,
        },
      ])
    } catch (error) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'Ошибка подключения к серверу' },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      <Conversation className="flex-1 px-4 py-6">
        <ConversationContent className="max-w-2xl mx-auto space-y-4">
          {messages.map((message, index) => (
            <div key={index}>
              {/* Tool calls перед ответом */}
              {message.tools_used?.map((tool, i) => (
                <Tool key={i} name={tool.name} className="mb-2">
                  <ToolTrigger>
                    {tool.name} ({tool.duration_ms.toFixed(0)}ms)
                  </ToolTrigger>
                  <ToolContent>
                    <pre className="text-xs overflow-auto">
                      {JSON.stringify(tool.result, null, 2)}
                    </pre>
                  </ToolContent>
                </Tool>
              ))}

              {/* Сообщение */}
              <Message from={message.role}>
                <MessageContent>
                  <MessageResponse>{message.content}</MessageResponse>
                </MessageContent>
              </Message>
            </div>
          ))}

          {isLoading && <Loader />}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      {/* Input */}
      <div className="px-4 py-4">
        <div className="max-w-2xl mx-auto">
          <PromptInput
            value={input}
            onValueChange={setInput}
            isLoading={isLoading}
            onSubmit={handleSubmit}
          >
            <PromptInputTextarea placeholder="Спроси о торговых данных..." />
            <PromptInputActions className="justify-end pt-2">
              <PromptInputAction tooltip={isLoading ? 'Остановить' : 'Отправить'}>
                <Button
                  variant="default"
                  size="icon"
                  className="h-8 w-8 rounded-full"
                  onClick={handleSubmit}
                  disabled={!input.trim() && !isLoading}
                >
                  {isLoading ? (
                    <Square className="size-4 fill-current" />
                  ) : (
                    <ArrowUp className="size-4" />
                  )}
                </Button>
              </PromptInputAction>
            </PromptInputActions>
          </PromptInput>
        </div>
      </div>
    </div>
  )
}
```

## Порядок работы

1. [ ] Установить AI Elements компоненты в frontend
2. [ ] Изменить `llm.py` - возвращать tool calls
3. [ ] Изменить `api.py` - новый response format
4. [ ] Обновить `page.tsx` - использовать новые компоненты
5. [ ] Тестирование локально
6. [ ] Деплой на сервер

## Ссылки

- [AI Elements Docs](https://ai-sdk.dev/elements)
- [Tool Component](https://ai-sdk.dev/elements/components/tool)
- [Chatbot Example](https://ai-sdk.dev/elements/examples/chatbot)
- [GitHub](https://github.com/vercel/ai-elements)
