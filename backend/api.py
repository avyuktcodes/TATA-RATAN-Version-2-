from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import sys
import os


# Ensure backend folder is in path so we can import query
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from query import query_engine

app = FastAPI(title="Tata Ratan API")

@app.on_event("startup")
def startup_event():
    import nest_asyncio
    nest_asyncio.apply()

# Allow React frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    print(f"Received query: {req.message}")
    
    try:
        # query_engine has streaming=True
        response = query_engine.query(req.message)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(error_trace)
        with open("logs/api_error.log", "w") as f:
            f.write(error_trace)
        raise e
    
    def generate():
        try:
            for text in response.response_gen:
                # Replace newlines so they don't break SSE framing
                safe_text = text.replace('\n', '<br>')
                yield f"data: {safe_text}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            print(f"Error during streaming: {e}")
            yield f"data: ERROR: {str(e)}\n\n"
            
    return StreamingResponse(generate(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
