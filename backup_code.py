"""
LiveKit Voice Agent with MySQL Context + Usage Metrics
======================================================
Loads agent instructions from MySQL, runs a multilingual voice session,
and aggregates usage metrics (LLM, TTS, STT) at shutdown.
"""

import os
import mysql.connector
import logging
from datetime import datetime
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, metrics, MetricsCollectedEvent
from livekit.plugins import openai, deepgram, silero, cartesia, sarvam
import json
# -------------------------------------------------------------------
# 🧱 Configuration & Logging
# -------------------------------------------------------------------
load_dotenv(".env.local")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_agent")

# -------------------------------------------------------------------
# 🧠 Database Helpers
# -------------------------------------------------------------------
def get_connection():
    """Create a MySQL connection."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "voice_agent"),
    )


def get_instructions_from_db():
    """Fetch the latest instruction context from MySQL."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT context FROM instruction ORDER BY id DESC LIMIT 1;")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            logger.info("✅ Loaded instructions from DB.")
            return result[0]
        else:
            logger.warning("⚠️ No instructions found. Using default.")
            return "You are a helpful multilingual assistant."
    except Exception as e:
        logger.error(f"❌ DB error while loading context: {e}")
        return "You are a helpful multilingual assistant."

import os

def calculate_cost(summary):
    """
    Calculate estimated cost in USD based on usage summary and rates.
    """
    # Load rates from environment
    llm_prompt_rate = float(os.getenv("LLM_PROMPT_COST_PER_1K", 0.0003))
    llm_completion_rate = float(os.getenv("LLM_COMPLETION_COST_PER_1K", 0.0006))
    stt_rate = float(os.getenv("STT_COST_PER_MIN", 0.004))
    tts_rate = float(os.getenv("TTS_COST_PER_1K_CHAR", 0.015))

    # Extract metrics safely
    prompt_tokens = getattr(summary, "llm_prompt_tokens", 0) or 0
    completion_tokens = getattr(summary, "llm_completion_tokens", 0) or 0
    stt_seconds = getattr(summary, "stt_audio_duration", 0.0) or 0.0
    tts_characters = getattr(summary, "tts_characters_count", 0) or 0

    # Compute per-service cost
    llm_cost = ((prompt_tokens / 1000) * llm_prompt_rate) + \
               ((completion_tokens / 1000) * llm_completion_rate)
    stt_cost = ((stt_seconds / 60) * stt_rate)
    tts_cost = ((tts_characters / 1000) * tts_rate)

    total_cost = llm_cost + stt_cost + tts_cost

    return {
        "llm_cost_usd": round(llm_cost, 6),
        "stt_cost_usd": round(stt_cost, 6),
        "tts_cost_usd": round(tts_cost, 6),
        "total_cost_usd": round(total_cost, 6)
    }

from datetime import datetime, timezone

def save_metrics_to_db(session_id, summary, start_time, end_time, costs):
    """Save usage metrics + cost into MySQL."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        llm_tokens = (summary.llm_prompt_tokens or 0) + (summary.llm_completion_tokens or 0)
        stt_seconds = summary.stt_audio_duration or 0.0
        tts_characters = summary.tts_characters_count or 0

        cursor.execute("""
            INSERT INTO session_metrics (
                session_id, start_time, end_time,
                llm_tokens, stt_seconds, tts_characters,
                llm_cost_usd, stt_cost_usd, tts_cost_usd, total_cost_usd
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session_id, start_time, end_time,
            llm_tokens, stt_seconds, tts_characters,
            costs["llm_cost_usd"], costs["stt_cost_usd"],
            costs["tts_cost_usd"], costs["total_cost_usd"]
        ))

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"✅ Metrics + Costs saved for {session_id}")
    except Exception as e:
        logger.error(f"❌ Failed to save metrics: {e}")




# -------------------------------------------------------------------
# 🗣️ TTS Loader
# -------------------------------------------------------------------
_tts = None
def _get_tts():
    global _tts
    if _tts is None:
        _tts = sarvam.TTS(
            target_language_code="hi-IN",
            speaker="manisha",
            model="bulbul:v2",
            pace=1.0,
            enable_preprocessing=True,
        )
    return _tts


# -------------------------------------------------------------------
# 🧠 Voice Assistant
# -------------------------------------------------------------------
class Assistant(Agent):
    """Voice assistant that loads its instructions dynamically."""
    def __init__(self):
        instructions = get_instructions_from_db()
        super().__init__(instructions=instructions)


# -------------------------------------------------------------------
# 🎙️ Entry Point
# -------------------------------------------------------------------
async def entrypoint(ctx: agents.JobContext):
    """Main entry for the LiveKit voice agent."""

    # Usage collector
    usage_collector = metrics.UsageCollector()
    start_time = datetime.now()

    # Create voice session
    session = AgentSession(
        stt=deepgram.STT(model="nova-3-general", language="multi"),
        llm=openai.LLM(model=os.getenv("LLM_CHOICE", "gpt-4.1-mini")),
        tts=cartesia.TTS(
            model="sonic-3",
            voice="faf0731e-dfb9-4cfc-8119-259a79b27e12",
            language="hi",
            speed=0.9,
            emotion="neutral",
        ),
        vad=silero.VAD.load(),
    )
    async def write_transcript():
        try:
            current_date = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"./transcript_{ctx.room.name}_{current_date}.json"

            # Get full message history
            history_dict = session.history.to_dict()
            items = history_dict.get("items", [])

            # Save JSON file
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(history_dict, f, indent=2, ensure_ascii=False)

            print(f"Transcript saved → {filename}")

            # ----- PAIRING LOGIC -----
            last_agent = None
            last_user = None

            conn = get_connection()
            cursor = conn.cursor()

            insert_sql = """
                INSERT INTO transcripts (session_id, agent, user, datetime)
                VALUES (%s, %s, %s, %s)
            """

            for item in items:
                if item.get("type") != "message":
                    continue

                role = item.get("role")
                text_list = item.get("content", [])
                text = text_list[0] if text_list else ""

                # Assistant spoke
                if role == "assistant":
                    last_agent = text

                # User replied
                elif role == "user":
                    last_user = text

                # When both agent+user exist → SAVE ROW
                if last_agent and last_user:
                    dt = datetime.now()

                    cursor.execute(insert_sql, (
                        session_id,
                        last_agent,
                        last_user,
                        dt
                    ))

                    # Reset after saving the pair
                    last_agent = None
                    last_user = None

            conn.commit()
            cursor.close()
            conn.close()

            logger.info("Paired transcript rows saved successfully.")

        except Exception as e:
            logger.error(f"ERROR writing transcript: {e}")


    ctx.add_shutdown_callback(write_transcript)
    # 🧩 Collect metrics on each event
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)

    # Unique session ID
    session_id = f"session_{ctx.room.name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    # 🎯 Log and save metrics at shutdown
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"📊 Final Usage Summary: {summary}")
        end_time = datetime.now()
        costs = calculate_cost(summary)
        logger.info(f"💰 Estimated Cost Breakdown: {costs}")

        save_metrics_to_db(session_id, summary, start_time, end_time, costs)


    ctx.add_shutdown_callback(log_usage)

    # Start the agent in the room
    await session.start(room=ctx.room, agent=Assistant())

    # Speak initial greeting
    await session.say("नमस्ते! मैं आपकी सहायता के लिए तैयार हूँ। बताइए, मैं आपकी कैसे मदद कर सकती हूँ?")

    # Wait until the session ends
    @session.on("close")
    def _on_session_close(ev):
        # Called when session finishes naturally
        summary = usage_collector.get_summary()
        costs = calculate_cost(summary)
        logger.info(f"📊 Final Usage Summary: {summary}")
        end_time = datetime.now()
        save_metrics_to_db(session_id, summary, start_time, end_time, costs)


# -------------------------------------------------------------------
# 🚀 Run the Agent
# -------------------------------------------------------------------
if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint)
    )
