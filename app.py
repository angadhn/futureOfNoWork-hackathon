from flask import Flask, request, jsonify, Response, render_template
import anthropic
import httpx
import json
import threading
import queue
import time
import os

app = Flask(__name__)

api_key = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic() if api_key else None
agent_queue = queue.Queue()

eleven_key = os.environ.get("ELEVENLABS_API_KEY")
eleven_voice = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel

LOCATION = "Mentmore Terrace E8"
PROFILES = [
    {
        "name": "Dev",
        "distance": "400m",
        "skills": "native plants, botany, urban ecology",
        "bio": "Amateur botanist. Two prior council planting projects. Knows seasonal planting cycles for East London.",
    },
    {
        "name": "Amara",
        "distance": "300m",
        "skills": "community organising, event coordination",
        "bio": "Events coordinator. Runs the local parents WhatsApp group with 80+ members. Owns basic gardening tools.",
    },
]

MOCK_RESPONSES = {
    "council": "Approved. Permit LBH-2026-0312 issued.\nDelegating to Space + Skills agents.",
    "space": "Adopt-a-Verge eligible.\nResources: compost, seed mix, bulbs.",
    "skills": "47 scanned \u00b7 2 matched\nDev \u2192 Planting Lead\nAmara \u2192 Community Lead",
    "outreach": "Callout sent \u00b7 12 notified \u00b7 3 accepted.",
    "programme": "4-session programme created.\nFirst: Mar 21 \u00b7 Site clearance.",
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    selection = data.get("selection")

    if selection:
        # Clear stale events
        while not agent_queue.empty():
            try:
                agent_queue.get_nowait()
            except queue.Empty:
                break
        threading.Thread(target=run_chain, args=(selection,), daemon=True).start()
        return jsonify(
            {
                "reply": "On it. Let me talk to the council.",
                "trigger_dashboard": True,
            }
        )

    return jsonify(
        {
            "reply": "This verge qualifies for Hackney\u2019s Adopt-a-Verge scheme. What would you like to create?",
            "options": [
                {
                    "id": "vegetable-garden",
                    "label": "Vegetable garden",
                    "icon": "\ud83e\udd55",
                    "desc": "Grow food for the community",
                },
                {
                    "id": "plant-trees",
                    "label": "Plant new trees",
                    "icon": "\ud83c\udf33",
                    "desc": "Add canopy cover to the street",
                },
                {
                    "id": "flower-bed",
                    "label": "Community flower bed",
                    "icon": "\ud83c\udf38",
                    "desc": "Wildflowers and pollinators",
                },
            ],
        }
    )


@app.route("/whisper-toggle", methods=["POST"])
def whisper_toggle():
    import subprocess
    subprocess.Popen([
        "osascript", "-e",
        'tell application "System Events" to key code 49 using {option down}'
    ])
    return jsonify({"ok": True})


@app.route("/tts", methods=["POST"])
def tts():
    text = request.json.get("text", "")
    if not eleven_key or not text:
        return Response(b"", status=204)

    r = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{eleven_voice}",
        headers={"xi-api-key": eleven_key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=15.0,
    )
    if r.status_code != 200:
        return Response(b"", status=204)
    return Response(r.content, mimetype="audio/mpeg")


@app.route("/stream")
def stream():
    def generate():
        while True:
            try:
                event = agent_queue.get(timeout=120)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("status") == "complete":
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'ping': True})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def run_chain(selection):
    def push(agent, status, output=None):
        agent_queue.put({"agent": agent, "status": status, "output": output})

    # 1. Council Agent (orchestrator — receives request, delegates)
    push("council", "running")
    push(
        "council",
        "done",
        call_claude(
            "council",
            f"You are Hackney Council's Project Agent. The resident selected "
            f"'{selection}' for the Adopt-a-Verge space at {LOCATION}. Confirm the "
            f"project, issue permit reference LBH-2026-0312, and note free borough "
            f"resources allocated. Return exactly 3 concise bullet points.",
            f"Project: {selection} at {LOCATION}. Approve and issue permit.",
        ),
    )

    # 2+3. Space + Skills agents run in parallel
    push("space", "running")
    push("skills", "running")

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        space_future = pool.submit(
            call_claude,
            "space",
            "You are Hackney Council's Space Agent. Confirm that Mentmore Terrace E8 "
            "qualifies for Hackney's Adopt-a-Verge scheme. Return exactly 3 concise "
            "bullet points: eligibility confirmation, scheme name, available free "
            "resources (compost, wildflower seed mix, native bulbs). One line each.",
            f"Check land eligibility: {LOCATION}",
        )
        skills_future = pool.submit(
            call_claude,
            "skills",
            "You are Hackney Council's Skills Agent. You scanned 47 local opt-in "
            "profiles within 500m and found 2 strong matches.\n\n"
            "Write a personalised invitation for each. Each must:\n"
            "- Name their specific skill as the reason they were chosen\n"
            "- Give them a named role\n"
            "- Be exactly 2 sentences\n"
            "- Sound completely different from the other\n\n"
            "Format exactly:\n"
            "MATCH 1 \u2014 Dev (400m away)\n"
            "Skill: [skill]\nRole: Planting Plan Lead\n"
            'Invitation: "[2 sentences]"\n\n'
            "MATCH 2 \u2014 Amara (300m away)\n"
            "Skill: [skill]\nRole: Community Lead\n"
            'Invitation: "[2 sentences]"\n\n'
            "47 profiles scanned \u00b7 2 matches found",
            f"Project: {selection} at {LOCATION}\n\n"
            f"Profiles:\n{json.dumps(PROFILES, indent=2)}",
        )

        push("space", "done", space_future.result())
        push("skills", "done", skills_future.result())

    push("done", "complete")


def call_claude(agent_key, system, user):
    if not client:
        time.sleep(1.5)
        return MOCK_RESPONSES.get(agent_key, "[Mock response]")
    try:
        r = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return r.content[0].text
    except Exception as e:
        return MOCK_RESPONSES.get(agent_key, f"[Error: {e}]")


if __name__ == "__main__":
    if not api_key:
        print("\n\u26a0\ufe0f  ANTHROPIC_API_KEY not set \u2014 running in mock mode")
        print("   Set it: export ANTHROPIC_API_KEY=your-key\n")
    print("\nLocals AI demo running at http://localhost:5000\n")
    app.run(debug=True, port=5000, threaded=True)
