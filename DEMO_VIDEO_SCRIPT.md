# Demo Video Script (target: 3:30-4:30)

Screen-recorded, narrated. Read the suggested lines or use your own words , the timing and beats matter more than the exact phrasing. Record the live app actually running, not a mockup.

---

**[0:00-0:20] Hook**

*(Face to camera or voiceover over a title card)*

> "When there's no photo of a crime suspect, an investigation depends entirely on a witness describing what they saw , usually to a scarce, expensive forensic sketch artist, or through a slow form that loses everything natural about how people actually describe faces. This is a voice-only AI that does that job live, built on Agora's Conversational AI Engine."

**[0:20-0:50] Architecture, briefly**

*(Show the README architecture diagram)*

> "Agora handles the entire real-time voice layer , listening, turn-taking, interruption, speaking back. Our backend never touches audio directly; it's just an endpoint Agora calls each turn. Behind that endpoint is a small multi-agent pipeline: feature extraction, contradiction detection, a jurisdiction lookup, composite sketch generation through Gemini, and a reconciliation agent for when there's more than one witness."

**[0:50-2:40] Live demo**

*(Screen recording of the actual app , this is the core of the video)*

1. Click **Begin interview** , narrate: "One click starts the case and the live call."
2. Describe a face out loud, a few features at a time. Let the sketch visibly build.
3. **Interrupt the agent mid-sentence.** Narrate over it: "It stops and adapts , that's real barge-in, not staged."
4. **Self-correct something already said.** Narrate: "And when I contradict myself, it catches it and asks , deterministically, this isn't left to chance, because it's a graded requirement, not a nice-to-have."
5. Let the read-back trigger, confirm it. Narrate: "Before anything is filed, it reads everything back for confirmation , separate from the human sign-off that comes next."
6. Open **Case tools**, sign off as a caseworker. Narrate: "Only now does the draft watermark disappear , the sketch is never presented as final until a human says so."
7. Trigger an escalation. Narrate: "And when something needs a human , distress, a conflict, uncertainty , it escalates, doesn't guess."

**[2:40-3:20] Safety framing**

*(Show the "AI limitations and safety considerations" section of the README, or say it over the app)*

> "This matters because the model never claims certainty it doesn't have , every locked feature keeps the witness's own words right next to the AI's interpretation, so nothing is hidden behind a clean-looking sketch. Reconciliation between witnesses works the same way: disagreement gets flagged for a human, never silently resolved."

**[3:20-3:50] Close**

> "Every real bug in this build , and there were several , got found and fixed through actual live testing, not assumptions. The architecture, the test suite, and the honest limitations are all in the README. Built for Build with Agora, Track 3."

*(End card: repo link, "mentions Agora")*

---

## Recording notes

- Do at least one full rehearsal run before recording , the live voice loop has real latency (~2s per turn plus ASR/TTS), so pacing narration around that beforehand avoids awkward dead air in the final cut.
- If the two-witness reconciliation path hasn't been rehearsed live and confirmed working, leave it out of the video rather than risk it failing on camera , the single-witness flow alone covers most of the mandatory requirements.
- Keep total runtime inside the 3-5 minute window , trim the architecture section first if running long, not the live demo itself.
