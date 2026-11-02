import os
import sys
import subprocess

# Ensure backend directory is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Ensure Playwright browser is installed in Linux environment
try:
    subprocess.run(["playwright", "install", "chromium"], check=False)
except Exception as e:
    print(f"[Startup] Playwright install notice: {e}")

import gradio as gr
from backend.main import app as fastapi_app

# Gradio custom interface wrapper
with gr.Blocks(title="AutoApply AI Agent", theme=gr.themes.Base()) as demo:
    gr.HTML("""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 40px 20px; background: #08090a; color: #f4f4f5; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08);">
        <div style="display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; border-radius: 12px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); margin-bottom: 16px;">
            <span style="color: #10b981; font-size: 24px; font-weight: bold;">⚡</span>
        </div>
        <h1 style="font-size: 24px; font-weight: 700; margin-bottom: 8px;">AutoApply Cloud API & Agent Operational</h1>
        <p style="color: #a1a1aa; font-size: 14px; max-width: 500px; margin: 0 auto 24px auto;">
            Autonomous job scouting, multi-tenant Supabase PostgreSQL persistence, and Google Gemini reasoning are active.
        </p>
        <div style="display: flex; gap: 12px; justify-content: center;">
            <a href="/" target="_blank" style="display: inline-block; background: #10b981; color: #08090a; padding: 10px 20px; border-radius: 8px; font-weight: 600; font-size: 13px; text-decoration: none;">
                Open Full Web Dashboard &rarr;
            </a>
            <a href="/api/health" target="_blank" style="display: inline-block; background: #18181b; color: #e4e4e7; border: 1px solid #27272a; padding: 10px 20px; border-radius: 8px; font-weight: 600; font-size: 13px; text-decoration: none;">
                API Health JSON
            </a>
        </div>
    </div>
    """)

# Mount FastAPI app onto Gradio
app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("app:fastapi_app", host="0.0.0.0", port=port, reload=False)
