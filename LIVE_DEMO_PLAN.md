# Live Demonstration Plan

A step-by-step script for demoing to judges live, ordered to hit as many of the 9 mandatory requirements as possible in one continuous flow, not as separate disconnected checks.

## Before the demo

- Confirm the backend is running, the ngrok tunnel is live, and `PUBLIC_BASE_URL` in `.env` matches the current tunnel URL (it changes every time ngrok restarts).
- Confirm `.env` has real Agora + Gemini credentials, and Gemini billing is active (image generation requires it).
- Open the frontend fresh , a hard refresh avoids any stale-cache issues.
- Have a backup phone/laptop hotspot ready in case venue wifi is unreliable.

## The flow (~4-5 minutes)

1. **Open with the premise, before touching the app.** "This is a witness describing a crime suspect they have no photo of. I'll talk to it live, the way a real witness would." This frames everything that follows.

2. **Click "Begin interview."** One click , case created, voice session started, agent joins and greets. Point out this is a single action, not a multi-step form.

3. **Describe a face naturally**, a few features at a time ("he had short black hair, kind of a square jaw, and a scar above his left eyebrow"). Let the sketch panel show the "Sketching…" animation and the first draft appear. Point at the feature chips populating and hover one to show the witness's own words alongside the interpreted value , the verified-vs-AI-interpretation separation, made visible, not just claimed.

4. **Interrupt it mid-sentence** while it's asking a follow-up question. This demonstrates barge-in live, not as a claim , judges should see it stop and adapt.

5. **Self-correct something already said** ("actually wait, his eyes were closer together than that"). This should trigger the Consistency Agent's clarifying question, verbatim-quoting both what was said before and now. This is the single clearest live demonstration of correction recovery and dynamic conversation flow , the two capabilities most tied to judging criteria for Conversational AI Depth.

6. **Keep going until the read-back triggers.** Once enough is captured, the agent reads everything back and asks for confirmation , point out this is a distinct step from the later human sign-off, not the same thing. Confirm it.

7. **Open "Case tools."** Show the case reference, the jurisdiction lookup (a real external action, not decorative), and sign it off as a caseworker , narrate that only now does the DRAFT watermark disappear.

8. **Trigger an escalation** , either say something that reads as distress, or just click "Escalate to human" directly with a reason. Point at the escalation banner appearing and (if Vobiz is configured) mention the real WhatsApp message this fires.

9. **If time allows and it's been tested beforehand**: start a second witness, describe the same suspect with one deliberately different feature, and reconcile , show the conflict banner. **Flag honestly to yourself before the event**: this path is unit-tested but has not been exercised live with two simultaneous real callers before this submission , rehearse it at least once beforehand, and if it's not reliable, skip it live rather than risk a visible failure, and instead point to the passing test suite as evidence it's built and verified at the logic level.

10. **Close on the architecture, not just the demo.** Pull up the README's architecture diagram and the "AI limitations and safety considerations" section , the point being that the safety framing (draft-only, human sign-off, fail-closed escalation) is a designed property of the system, not an afterthought.

## If something goes wrong live

- **No transcript / agent seems unresponsive**: give it a clear, complete sentence and a natural pause , the turn-detection is tuned to wait for real silence before finalizing, so short fragments or immediate re-speaking can confuse it.
- **Sketch doesn't update**: check the sketching overlay , if it's stuck on "Sketching…", the background generation may have hit a real API failure; the system is designed to mark this `GENERATION_FAILED` and keep the last good image rather than show nothing, so a stale-but-present sketch is expected behavior, not a bug.
- **Full technical failure**: fall back to walking through the codebase and the 43 passing tests directly , the architecture and the engineering discipline behind it (resilience contract, fail-open/fail-closed design, real bugs found and fixed via live debugging) is itself a strong story even without a perfect live run.
