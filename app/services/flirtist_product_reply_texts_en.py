from __future__ import annotations

from typing import assert_never

from app.services.flirtist_product_reply_context import ReplyContext, focus_or_topic


def en_reply_texts(style: str, context: ReplyContext, focus: str | None) -> list[str]:
    topic = focus_or_topic(context.topic, focus)
    match context.scenario:
        case "celebration":
            table = {
                "genuine": [
                    "That is huge. I am genuinely happy for you.",
                    "Finally being done must feel amazing. You deserve to enjoy that win tonight.",
                    f"Passing {topic} is absolutely worth celebrating.",
                    "I am smiling at my phone right now. Big congrats.",
                    "That kind of win deserves more than a text, but this is my start: I am proud of you.",
                ],
                "nsfw": [
                    "Careful, good news makes me want to celebrate you in person.",
                    "That win deserves a dangerous amount of attention from me.",
                    "I can say congrats politely, but I would rather say it closer.",
                    "You being proud of yourself is unfairly attractive.",
                    "Let me know when I am allowed to make that celebration less innocent.",
                ],
                "flirty": [
                    "That deserves a proper celebration. Can I be part of it?",
                    "Huge congrats. I think a victory drink with me is only fair.",
                    "You did the hard part, so I can handle the celebration plan.",
                    "I want to hear the full story while buying you something good.",
                    "That win looks good on you. Let me celebrate it with you.",
                ],
                "witty": [
                    "Achievement unlocked. Now we need a reward scene.",
                    "You beat the boss level. I volunteer as the celebration side quest.",
                    "That is not just news, that is scoreboard material.",
                    "The correct response is obviously applause and snacks.",
                    "I will keep this brief: legend behavior.",
                ],
                "romantic": [
                    "I am really happy for you. I hope you let yourself feel proud tonight.",
                    "That is such good news. I wish I could see your face while you tell me.",
                    "You worked for this, and I am glad it finally paid off.",
                    "I love that you shared that with me. Congratulations, really.",
                    "That win deserves a soft night and someone being fully happy for you.",
                ],
            }
        case "reaction":
            table = _en_reaction_table(topic)
        case "affection":
            table = _en_affection_table(topic)
        case "fatigue" | "plans" | "generic":
            table = _en_generic_table(topic)
        case unreachable:
            assert_never(unreachable)
    return table.get(style, table["genuine"])


def _en_reaction_table(topic: str) -> dict[str, list[str]]:
    return {
        "genuine": [
            f"Okay, now I am curious about {topic}. What made it that good?",
            "No spoilers, but give me the one-line pitch.",
            "That reaction makes me want to watch it too. Best part?",
            "I trust that review more than a trailer. What did you like most?",
            "That sounds worth adding to my list. What kind of vibe was it?",
        ],
        "nsfw": [
            "Careful, hearing you get excited about something is very distracting.",
            f"I want the {topic} review, but I might be more interested in watching your reaction.",
            "No spoilers. I would rather hear it from you in person.",
            "That little burst of excitement is unfairly cute.",
            "If your recommendation is that convincing, I may need a private screening.",
        ],
        "flirty": [
            f"If {topic} passed your test, I should probably watch it. Want to compare notes after?",
            "Now I want your full recommendation list.",
            "That made me curious about your taste. Give me one more pick.",
            "I like how excited you sound. That alone kind of sells it.",
            "I will watch it if I get your commentary after.",
        ],
        "witty": [
            "That is a dangerous review. My watchlist just got longer.",
            "No-spoiler sales pitch, go.",
            "Okay, critic mode activated. What score are we giving it?",
            "This sounds like a recommendation with evidence. I respect it.",
            "You cannot say it was that good and leave me with no details.",
        ],
        "romantic": [
            "I like hearing what you get excited about. What stayed with you after?",
            "That makes me want to know your taste better.",
            "Tell me the part you loved most. I like seeing how you see things.",
            "The way you said that makes me want to watch it through your eyes.",
            "Next time, I would like to hear the full review from you properly.",
        ],
    }


def _en_affection_table(topic: str) -> dict[str, list[str]]:
    return {
        "genuine": [
            "Wait, now I need to know what made you think of me.",
            "That is weirdly sweet. What was the moment?",
            "I like that. Tell me the funny part though.",
            "You cannot say I randomly crossed your mind and then not explain.",
            "That little detail is cute. What sparked it?",
        ],
        "nsfw": [
            "Careful, saying I was on your mind gives me ideas.",
            "That is a dangerous thing to tell me without details.",
            "Now I am going to wonder exactly what kind of thought it was.",
            "If I was on your mind, I am going to need the full story.",
            "That message is a little too good at getting my attention.",
        ],
        "flirty": [
            "I like being the random thought of the day. What triggered it?",
            "That made me smile more than it should have.",
            "Okay, that is cute. What were you doing when I popped up?",
            "I will take being remembered, especially if there is a funny story attached.",
            "That sounds like the start of a good story. Tell me.",
        ],
        "witty": [
            "I need the case file: time, place, and why I appeared.",
            "Was this a compliment or an incident report?",
            "I accept this mysterious cameo. Please explain the plot.",
            "That is too vague. I need the director's cut.",
            "Randomly thinking of me is either sweet or suspicious. Which one?",
        ],
        "romantic": [
            "That is the kind of small message that stays with me.",
            "I like knowing I crossed your mind. What was happening?",
            "That is sweet in a quiet way. Tell me the moment.",
            "Now I am smiling at my phone a little.",
            "I like being part of your day, even randomly.",
        ],
    }


def _en_generic_table(topic: str) -> dict[str, list[str]]:
    return {
        "genuine": [
            "Wait, I need the context. What happened right before that?",
            "That sounds like there is a story behind it. What happened?",
            "Okay, you have my attention. What was the moment?",
            "I want the one-sentence backstory now.",
            "That is specific enough that I need details.",
        ],
        "nsfw": [
            "Careful, that made me more curious than I planned to be.",
            "This conversation could get dangerously fun if we keep going.",
            "I like this tension a little too much.",
            "I can keep behaving, but you are not making it easy.",
            "Tell me more before I start flirting worse.",
        ],
        "flirty": [
            "Now I am curious about you in a way I should probably admit.",
            "I like how this conversation feels. Keep going?",
            "That makes me want to steal more of your time.",
            "You have my attention now.",
            "I would rather hear this from you in person.",
        ],
        "witty": [
            "Okay, that needs a second episode.",
            "You cannot drop that and expect no follow-up questions.",
            "I am officially invested now.",
            "That is a dangerous amount of curiosity you just created.",
            "I was normal before this message, probably.",
        ],
        "romantic": [
            "I like when you tell me things like that.",
            "That makes me want to understand you better.",
            "No rush. I like hearing your thoughts at your pace.",
            "That felt honest. I appreciate that.",
            "I am glad you shared that with me.",
        ],
    }
