from __future__ import annotations

from typing import assert_never

from app.schemas.flirtist import FlirtistLanguage


def language_name(language: FlirtistLanguage) -> str:
    match language:
        case "en":
            return "English (United States)"
        case "ko":
            return "Korean"
        case "ja":
            return "Japanese"
        case "zh-Hant":
            return "Traditional Chinese"
        case "es-MX":
            return "Mexican Spanish"
        case "pt-BR":
            return "Brazilian Portuguese"
        case "fr":
            return "French"
        case "de":
            return "German"
        case "th":
            return "Thai"
        case "id":
            return "Indonesian"
        case unreachable:
            assert_never(unreachable)


def culture_guidance(language: FlirtistLanguage) -> str:
    match language:
        case "en":
            return (
                "Use casual US texting. Keep it warm, specific, lightly playful, and never like a pickup-line template."
            )
        case "ko":
            return (
                "Use native Korean KakaoTalk/Instagram DM rhythm. Preserve 존댓말/반말, avoid 당신, and keep replies short and alive."
            )
        case "ja":
            return (
                "Use natural Japanese LINE tone. Avoid overly direct confessions, keep distance polite unless the chat is clearly casual, and prefer soft endings like ね/かな when appropriate."
            )
        case "zh-Hant":
            return (
                "Use Traditional Chinese for Taiwan/Hong Kong style chat. Keep it concise, warm, and not too pushy; avoid Simplified Chinese wording."
            )
        case "es-MX":
            return (
                "Use Mexican Spanish WhatsApp tone. Sound relaxed and natural, avoid Spain-only phrasing, and keep flirting playful rather than intense."
            )
        case "pt-BR":
            return (
                "Use Brazilian Portuguese WhatsApp tone. Keep it light, warm, and conversational; avoid European Portuguese phrasing."
            )
        case "fr":
            return (
                "Use natural French texting. Keep it understated, charming, and not overly enthusiastic; avoid literal English rhythm."
            )
        case "de":
            return (
                "Use natural German chat tone. Be clear, warm, and low-pressure; avoid cheesy escalation and over-formal wording."
            )
        case "th":
            return (
                "Use natural Thai chat tone. Keep it gentle, playful, and face-saving; avoid blunt pressure and overly formal textbook Thai."
            )
        case "id":
            return (
                "Use natural Indonesian chat tone. Keep it friendly, light, and not too intense; avoid stiff formal Indonesian unless the chat is formal."
            )
        case unreachable:
            assert_never(unreachable)


def analysis_title(language: FlirtistLanguage) -> str:
    match language:
        case "en":
            return "Chat Wrapped"
        case "ko":
            return "대화 분석"
        case "ja":
            return "チャット分析"
        case "zh-Hant":
            return "聊天分析"
        case "es-MX":
            return "Análisis del chat"
        case "pt-BR":
            return "Análise do chat"
        case "fr":
            return "Analyse du chat"
        case "de":
            return "Chat-Analyse"
        case "th":
            return "วิเคราะห์แชต"
        case "id":
            return "Analisis chat"
        case unreachable:
            assert_never(unreachable)


def reply_headline(language: FlirtistLanguage) -> str:
    match language:
        case "en":
            return "AI generated rizz"
        case "ko":
            return "AI 추천 답장"
        case "ja":
            return "AIおすすめ返信"
        case "zh-Hant":
            return "AI 推薦回覆"
        case "es-MX":
            return "Respuestas sugeridas por IA"
        case "pt-BR":
            return "Respostas sugeridas por IA"
        case "fr":
            return "Réponses suggérées par l’IA"
        case "de":
            return "KI-Antwortvorschläge"
        case "th":
            return "คำตอบที่ AI แนะนำ"
        case "id":
            return "Balasan rekomendasi AI"
        case unreachable:
            assert_never(unreachable)


def reply_pack_specs(language: FlirtistLanguage) -> list[tuple[str, str, str, str]]:
    match language:
        case "ko":
            return [
                ("genuine", "자연스럽게", "자연스러운 답장", "bolt.fill"),
                ("nsfw", "아슬하게", "아슬한 텐션", "flame.fill"),
                ("flirty", "은근 설레게", "은근한 플러팅", "heart.fill"),
                ("witty", "센스있게", "센스 있는 답장", "sparkles"),
                ("romantic", "다정하게", "다정한 답장", "heart.circle.fill"),
            ]
        case "ja":
            return [
                ("genuine", "自然に", "自然な返信", "bolt.fill"),
                ("nsfw", "少し攻める", "少し攻めた返信", "flame.fill"),
                ("flirty", "さりげなく好意", "さりげない返信", "heart.fill"),
                ("witty", "気の利いた", "気の利いた返信", "sparkles"),
                ("romantic", "やさしく", "やさしい返信", "heart.circle.fill"),
            ]
        case "zh-Hant":
            return [
                ("genuine", "自然", "自然回覆", "bolt.fill"),
                ("nsfw", "更曖昧", "更有張力的回覆", "flame.fill"),
                ("flirty", "輕鬆調情", "調情回覆", "heart.fill"),
                ("witty", "機智", "機智回覆", "sparkles"),
                ("romantic", "溫柔", "溫柔回覆", "heart.circle.fill"),
            ]
        case "es-MX":
            return [
                ("genuine", "Natural", "Respuestas naturales", "bolt.fill"),
                ("nsfw", "Más atrevido", "Respuestas con más tensión", "flame.fill"),
                ("flirty", "Coqueto", "Respuestas coquetas", "heart.fill"),
                ("witty", "Ingenioso", "Respuestas ingeniosas", "sparkles"),
                ("romantic", "Cálido", "Respuestas cálidas", "heart.circle.fill"),
            ]
        case "pt-BR":
            return [
                ("genuine", "Natural", "Respostas naturais", "bolt.fill"),
                ("nsfw", "Mais ousado", "Respostas mais ousadas", "flame.fill"),
                ("flirty", "Com flerte", "Respostas com flerte", "heart.fill"),
                ("witty", "Esperto", "Respostas espertas", "sparkles"),
                ("romantic", "Carinhoso", "Respostas carinhosas", "heart.circle.fill"),
            ]
        case "fr":
            return [
                ("genuine", "Naturel", "Réponses naturelles", "bolt.fill"),
                ("nsfw", "Plus direct", "Réponses plus directes", "flame.fill"),
                ("flirty", "Flirt léger", "Réponses flirty", "heart.fill"),
                ("witty", "Malin", "Réponses malines", "sparkles"),
                ("romantic", "Chaleureux", "Réponses chaleureuses", "heart.circle.fill"),
            ]
        case "de":
            return [
                ("genuine", "Natürlich", "Natürliche Antworten", "bolt.fill"),
                ("nsfw", "Mutiger", "Mutigere Antworten", "flame.fill"),
                ("flirty", "Flirty", "Flirty Antworten", "heart.fill"),
                ("witty", "Schlagfertig", "Schlagfertige Antworten", "sparkles"),
                ("romantic", "Warm", "Warme Antworten", "heart.circle.fill"),
            ]
        case "th":
            return [
                ("genuine", "เป็นธรรมชาติ", "คำตอบแบบธรรมชาติ", "bolt.fill"),
                ("nsfw", "กล้าขึ้น", "คำตอบที่มีแรงดึงดูด", "flame.fill"),
                ("flirty", "หยอดเบา ๆ", "คำตอบแนวจีบ", "heart.fill"),
                ("witty", "มีไหวพริบ", "คำตอบฉลาด ๆ", "sparkles"),
                ("romantic", "อบอุ่น", "คำตอบอบอุ่น", "heart.circle.fill"),
            ]
        case "id":
            return [
                ("genuine", "Natural", "Balasan natural", "bolt.fill"),
                ("nsfw", "Lebih berani", "Balasan lebih berani", "flame.fill"),
                ("flirty", "Menggoda ringan", "Balasan menggoda", "heart.fill"),
                ("witty", "Cerdas", "Balasan cerdas", "sparkles"),
                ("romantic", "Hangat", "Balasan hangat", "heart.circle.fill"),
            ]
        case "en":
            return [
                ("genuine", "Natural", "Natural replies", "bolt.fill"),
                ("nsfw", "Bold", "Bolder replies", "flame.fill"),
                ("flirty", "Flirty", "Flirty replies", "heart.fill"),
                ("witty", "Witty", "Witty replies", "sparkles"),
                ("romantic", "Warm", "Warm replies", "heart.circle.fill"),
            ]
        case unreachable:
            assert_never(unreachable)
