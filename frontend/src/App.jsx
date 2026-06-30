import React, { useState, useRef, useEffect } from 'react';
import './App.css';
import Excavator from './components/Excavator';

function App() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Welcome to the Tata_Ratan GraphRAG Engine. What can I help you with today?' }
  ]);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  
  const endOfMessagesRef = useRef(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsThinking(true);
    
    // Add empty assistant message to stream into
    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      let isFirstChunk = true;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        if (isFirstChunk) {
          setIsThinking(false);
          isFirstChunk = false;
        }

        const chunk = decoder.decode(value, { stream: true });
        
        // SSE format: data: text\n\n
        const lines = chunk.split('\n');
        for (let line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
                break;
            }
            if (data.startsWith('ERROR:')) {
                setMessages(prev => {
                    const newMessages = [...prev];
                    newMessages[newMessages.length - 1].content = data;
                    return newMessages;
                });
                break;
            }
            // Replace <br> back to newlines for rendering
            const cleanData = data.replace(/<br>/g, '\n');
            setMessages(prev => {
              const newMessages = [...prev];
              newMessages[newMessages.length - 1].content += cleanData;
              return newMessages;
            });
          }
        }
      }
    } catch (error) {
      console.error("Error fetching chat stream:", error);
      setIsThinking(false);
      setMessages(prev => {
          const newMessages = [...prev];
          newMessages[newMessages.length - 1].content = "Connection error. Make sure the FastAPI backend is running on port 8000.";
          return newMessages;
      });
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <div className="app-container">
      <header className="corporate-header">
        <h1>Tata Ratan <span>GraphRAG Intelligence</span></h1>
      </header>
      
      <main className="chat-interface">
        <div className="chat-history">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message-bubble ${msg.role}`}>
              <div className="message-sender">{msg.role === 'user' ? 'You' : 'Tata Ratan AI'}</div>
              <div className="message-content" dangerouslySetInnerHTML={{ __html: msg.content.replace(/\n/g, '<br/>') }} />
            </div>
          ))}
          {isThinking && <Excavator />}
          <div ref={endOfMessagesRef} />
        </div>
        
        <form onSubmit={handleSubmit} className="chat-input-form">
          <input 
            type="text" 
            value={input} 
            onChange={(e) => setInput(e.target.value)} 
            placeholder="Ask a deep question about Tata Steel's graph schema..." 
            disabled={isThinking}
          />
          <button type="submit" disabled={isThinking || !input.trim()}>Submit</button>
        </form>
      </main>
    </div>
  );
}

export default App;
