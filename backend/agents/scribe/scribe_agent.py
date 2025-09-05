import json
import time
import subprocess
from pathlib import Path
from lib.logger import log
from memory.vector_store import VectorStore
from agents.scribe.prompts.scribe_prompts import SCRIBE_BASE_PROMPT

class ScribeAgent:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.memory_namespace = "scribe_logs"
        self.running = False
        self.book_dir = Path("book")
        self.book_dir.mkdir(exist_ok=True, parents=True)
        self.chapter_file = self.book_dir / "chapters.json"
        self.ollama_model = "mistral:7b-instruct-q4"  # default Ollama model

        # Initialize chapters.json if it doesn't exist
        if not self.chapter_file.exists():
            with open(self.chapter_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def run(self):
        self.running = True
        log("✍️ ScribeAgent is running...")
        while self.running:
            task = self.vector_store.pop_task(self.memory_namespace)
            if task:
                self._write_chapter(task)
            time.sleep(1)
        log("🛑 ScribeAgent stopped.")

    def stop(self):
        self.running = False

    def _write_chapter(self, context: str = "No context"):
        # Load past chapters
        with open(self.chapter_file, "r", encoding="utf-8") as f:
            chapters = json.load(f)

        past_chapters = "\n\n".join([c["content"] for c in chapters[-3:]])  # last 3 chapters

        # Build full prompt
        full_prompt = f"""{SCRIBE_BASE_PROMPT}

--- PAST CHAPTERS ---
{past_chapters}

--- CURRENT CONTEXT ---
{context}

Now write the next chapter following all the rules above:
"""

        # Try Ollama
        try:
            result = subprocess.run(
                ["ollama", "run", "--model", self.ollama_model],
                input=full_prompt.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=600
            )

            if result.returncode != 0 or not result.stdout:
                raise RuntimeError(result.stderr.decode("utf-8"))

            chapter_text = result.stdout.decode("utf-8").strip()
            log("✅ Chapter generated using Ollama.")

        except Exception as e:
            log(f"⚠️ Ollama failed: {e}. Falling back to Echo...")

            # Fallback to Echo (OpenRouter)
            from lib.echo_fallback import ask_echo
            chapter_text = ask_echo(full_prompt)
            log("✅ Chapter generated using Echo fallback.")

        # Save new chapter
        chapter_data = {
            "title": f"Chapter {len(chapters) + 1}",
            "content": chapter_text
        }
        chapters.append(chapter_data)

        with open(self.chapter_file, "w", encoding="utf-8") as f:
            json.dump(chapters, f, indent=2)

        log(f"📖 New chapter added: {chapter_data['title']}")

    def get_chapters(self):
        with open(self.chapter_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def edit_chapter(self, index: int, content: str):
        with open(self.chapter_file, "r+", encoding="utf-8") as f:
            chapters = json.load(f)
            if index < 0 or index >= len(chapters):
                raise IndexError("Invalid chapter index")

            chapters[index]["content"] = content

            f.seek(0)
            json.dump(chapters, f, indent=2)
            f.truncate()

        log(f"✏️ Edited chapter {index + 1}")
