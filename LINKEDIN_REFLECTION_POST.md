Spent yesterday at Knotic's Build with Agora buildathon, and it was one of the most intense single days of building I've done in a while.

The challenge: build a voice-native AI agent on Agora's Conversational AI Engine, solo, in one day. I built a Composite Sketch Assistant, an AI that has a live voice conversation with a crime witness, builds a composite sketch as they describe a suspect, catches contradictions in what they say, and reconciles multiple witnesses' accounts when they disagree instead of silently picking one.

(Yes, the repo name is extremely literal: github.com/88h88h/voice-enabled-composite-CrimeSuspect-drawing-agentic-system. No regrets.)

I didn't win. But the day was worth it for what actually got built and debugged live: a real multi-agent pipeline behind the voice layer, a full resilience system where every agent has a deliberate fail-open or fail-closed behavior depending on what's at stake, and more live production-style bugs than I expected to hit and fix in one sitting. A silently wrong ASR vendor config that produced zero transcripts despite the agent reporting healthy. A missing field in the streaming response format. Voice-activity-detection tuning that was cutting people off mid-sentence. Nothing about it was theoretical by the end of the day, it actually worked, live, with real voice.

Genuinely grateful to Knotic and the judges for putting this together, and to everyone building alongside me. On to the next one.

#BuildWithAgora #Agora #VoiceAI #ConversationalAI #buildinpublic
