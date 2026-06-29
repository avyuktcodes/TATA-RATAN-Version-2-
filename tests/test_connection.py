import ollama
try:
    response = ollama.chat(model='llama3.1', messages=[{'role': 'user', 'content': 'Hello'}])
    print("Success! The AI replied:", response['message']['content'])
except Exception as e:
    print("Connection Failed:", e)