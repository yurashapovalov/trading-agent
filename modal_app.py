"""Modal deployment for Trading Agent API"""

import modal

# Create app
app = modal.App("trading-agent")

# Create volume for DuckDB data
volume = modal.Volume.from_name("trading-data", create_if_missing=True)

# Docker image with dependencies + copy local code
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "anthropic",
        "duckdb",
        "pandas",
        "python-dotenv",
        "fastapi",
        "sse-starlette",
    )
    .add_local_python_source("agent")
    .add_local_python_source("data")
    .add_local_python_source("config")
)


# Create FastAPI app with proper routing
def create_fastapi_app():
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from sse_starlette.sse import EventSourceResponse
    import os
    import json

    # Set environment BEFORE any imports that use config
    os.environ["DATABASE_PATH"] = "/data/trading.duckdb"
    import config
    config.DATABASE_PATH = "/data/trading.duckdb"

    web_app = FastAPI(title="Trading Agent API")

    # CORS
    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @web_app.get("/health")
    async def health():
        return {"status": "ok", "service": "Trading Agent on Modal"}

    @web_app.get("/data/info")
    async def data_info():
        from data import get_data_info
        df = get_data_info(db_path="/data/trading.duckdb")
        if df.empty:
            return []
        return [
            {
                "symbol": row["symbol"],
                "bars": int(row["bars"]),
                "start_date": str(row["start_date"])[:10],
                "end_date": str(row["end_date"])[:10],
                "trading_days": int(row["trading_days"])
            }
            for _, row in df.iterrows()
        ]

    @web_app.post("/chat/stream")
    async def chat_stream(request: Request):
        from agent.llm import TradingAgent

        body = await request.json()
        message = body.get("message", "")

        if not message:
            return JSONResponse({"error": "No message provided"}, status_code=400)

        async def generate():
            try:
                agent = TradingAgent()
                result = agent.chat(message)

                response_text = result["response"]
                tools_used = result.get("tools_used", [])

                # Send tools info first
                if tools_used:
                    yield {
                        "event": "tool",
                        "data": json.dumps({"tools": tools_used})
                    }

                # Stream the response in chunks
                chunk_size = 50
                for i in range(0, len(response_text), chunk_size):
                    chunk = response_text[i:i + chunk_size]
                    yield {
                        "event": "message",
                        "data": json.dumps({"content": chunk})
                    }

                # Done
                yield {
                    "event": "done",
                    "data": json.dumps({"status": "complete"})
                }

            except Exception as e:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(e)})
                }

        return EventSourceResponse(generate())

    return web_app


@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("anthropic-key")],
    timeout=300,
)
@modal.asgi_app()
def fastapi_app():
    return create_fastapi_app()


# CLI to upload data
@app.local_entrypoint()
def main():
    """Upload DuckDB file to Modal volume."""
    import subprocess

    print("Uploading trading.duckdb to Modal volume...")
    subprocess.run([
        "modal", "volume", "put", "trading-data",
        "data/trading.duckdb", "/trading.duckdb"
    ])
    print("Done!")
