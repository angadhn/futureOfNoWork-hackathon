# Locals AI — Agent Orchestration Proof of Concept

Built at the [Future of (No) Work Hackathon](https://luma.com/emtfkvtj?tk=QfIkik) (15 Mar 2026, London) — **Track 1: Human Flourishing**.

The track challenge: *take a real person in London from screen time to real-world action* by building an agentic product that demonstrates the complete workflow.

## What this is

A proof of concept for an **agent orchestration flow** — not a production app. It demonstrates how a network of AI agents (Council, Space, Skills) coordinate to turn a resident's intent ("I want to plant a community garden") into a real-world project with permits, matched volunteers, and a programme.

The core idea: each person has a personal AI agent that interfaces with council agents and the agents of nearby residents. This prototype sketches that orchestration — the cascade from request → approval → resource matching → skill matching → outreach — as a running demo.

## Running it

```bash
git clone https://github.com/angadhn/futureOfNoWork-hackathon.git
cd futureOfNoWork-hackathon
pip install -r requirements.txt
python app.py
```

This starts a Flask server at `http://localhost:5000`.

By default it runs in **mock mode** (no API keys needed — agents return canned responses). To use live Claude and ElevenLabs TTS:

```bash
export ANTHROPIC_API_KEY=your-key
export ELEVENLABS_API_KEY=your-key    # optional, for voice output
python app.py
```

## Team

- [Zuzana Kapustikova](https://www.linkedin.com/in/zuzanakapustikova/)
- [Lexa Gallery](https://www.linkedin.com/in/lexagallery/)
