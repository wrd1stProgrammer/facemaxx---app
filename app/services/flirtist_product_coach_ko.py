from __future__ import annotations

from typing import Literal, assert_never

CoachIntent = Literal[
    "bar_approach",
    "old_crush_drinks",
    "coffee_approach",
    "slow_reply",
    "first_contact",
    "blind_date",
    "after_date",
    "profile_compliment",
    "texting_pace",
    "confession_timing",
    "low_pressure_flirt",
    "meetup",
    "generic",
]


def ko_intent(message: str) -> CoachIntent:
    if _mentions(message, ("커피", "카페", "coffee")):
        return "coffee_approach"
    if _mentions(message, ("2년", "오랜만", "썸녀", "썸남", "술 먹", "한잔", "술먹")):
        return "old_crush_drinks"
    if _mentions(message, ("헌팅포차", "포차", "술집", "클럽", "번따")):
        return "bar_approach"
    if _mentions(message, ("느려", "답장", "읽씹", "reply", "slow")):
        return "slow_reply"
    if _mentions(message, ("선톡", "먼저 연락", "먼저 톡")):
        return "first_contact"
    if _mentions(message, ("소개팅", "만나기 전", "첫 만남")):
        return "blind_date"
    if _mentions(message, ("첫 데이트", "데이트 후", "after date", "first date")):
        return "after_date"
    if _mentions(message, ("프로필", "사진", "셀카", "칭찬")):
        return "profile_compliment"
    if _mentions(message, ("연락", "빈도", "카톡", "톡 텀", "텀")):
        return "texting_pace"
    if _mentions(message, ("고백", "타이밍", "사귀", "관계 확정")):
        return "confession_timing"
    if _mentions(message, ("플러팅", "부담", "연습", "장난")):
        return "low_pressure_flirt"
    if _mentions(message, ("약속", "만남", "일정", "시간")):
        return "meetup"
    return "generic"


def ko_answer(context_hint: str, intent: CoachIntent, message: str) -> str:
    match intent:
        case "bar_approach":
            return (
                f"{context_hint}헌팅포차면 첫마디는 짧고 빠져나갈 길이 있어야 자연스러워요. "
                "이렇게 말해봐요: \"친구들이랑 오셨어요? 분위기 좋아 보여서 한마디만 걸어봤어요. 불편하면 바로 갈게요.\" "
                "웃으면서 받아주면 이름이나 메뉴 얘기로 30초만 이어가고, 반응이 닫히면 바로 빠지세요."
            )
        case "old_crush_drinks":
            return (
                f"{context_hint}2년 전 썸이면 바로 술 약속부터 박기보다, 오랜만이라는 어색함을 먼저 녹이는 게 좋아요. "
                "보낼 문장은 이 정도: \"오랜만이야 ㅋㅋ 갑자기 생각나서 연락했어. 요즘 어떻게 지내? 시간 맞으면 가볍게 한잔하면서 근황 듣고 싶다.\" "
                "답이 오면 그때 날짜 두 개만 제안하세요."
            )
        case "coffee_approach":
            return (
                f"{context_hint}카페나 커피숍에서는 외모 칭찬보다 같은 공간 핑계가 훨씬 덜 부담스러워요. "
                "첫마디는 \"혹시 여기 자주 오세요? 메뉴 고르다 실패 중이라 추천 하나만 받고 싶어서요\" 정도가 좋아요. "
                "상대가 짧게 답하면 고맙다고 끝내고, 웃으면 이름이나 자리 얘기로 이어가세요."
            )
        case "slow_reply":
            return (
                f"{context_hint}답장이 느릴 땐 확인받으려는 톡을 더 보내면 압박처럼 보여요. "
                "마지막 대화에 붙여서 \"ㅋㅋ 그건 인정. 바쁠 때 말고 편할 때 얘기 더 들려줘\" 정도로 한 번만 보내세요."
            )
        case "first_contact":
            return (
                f"{context_hint}선톡은 명분이 있으면 훨씬 자연스러워요. "
                "\"아까 말한 거 갑자기 생각났어 ㅋㅋ 그래서 결국 어떻게 됐어?\"처럼 이전 대화 하나를 잡고 가볍게 여세요."
            )
        case "blind_date":
            return (
                f"{context_hint}소개팅 전엔 센스 증명보다 약속을 편하게 만드는 문자가 좋아요. "
                "\"내일 7시 맞지? 가는 길 조심히 와. 메뉴는 만나서 같이 골라보자\"처럼 확인과 배려만 짧게 넣으세요."
            )
        case "after_date":
            return (
                f"{context_hint}첫 데이트 후엔 평가보다 기억나는 장면 하나가 더 설레요. "
                "\"오늘 네가 말한 그 얘기 계속 생각나더라 ㅋㅋ 조심히 들어갔어?\" 정도면 여운도 있고 부담도 낮아요."
            )
        case "profile_compliment":
            return (
                f"{context_hint}사진 칭찬은 외모 평가처럼 들리면 부담스러워요. "
                "\"사진 분위기 좋다. 저기 어디야?\"처럼 분위기나 장소를 짚고 질문 하나만 붙이세요."
            )
        case "texting_pace":
            return (
                f"{context_hint}연락 텀은 정답을 맞히려 하기보다 서로 편한 속도를 확인하는 게 좋아요. "
                "\"나는 답장 텀이 좀 들쭉날쭉한 편인데, 너는 연락 어떻게 하는 게 편해?\"처럼 내 기준을 먼저 열어주세요."
            )
        case "confession_timing":
            return (
                f"{context_hint}고백 타이밍은 말의 완성도보다 최근 만남의 온도가 먼저예요. "
                "다음 약속이 자연스럽게 잡히고 스킨십/연락 반응이 안정적이면, 길게 돌리지 말고 \"나 너랑 더 진지하게 만나보고 싶어\" 정도가 좋아요."
            )
        case "low_pressure_flirt":
            return (
                f"{context_hint}부담 낮은 플러팅은 칭찬 하나에 장난스러운 질문 하나면 충분해요. "
                "\"그 말투 은근 중독성 있는데? 원래 그렇게 사람 헷갈리게 해?\"처럼 웃고 넘길 여지를 남기세요."
            )
        case "meetup":
            return (
                f"{context_hint}약속 제안은 선택지를 좁혀줘야 답하기 쉬워요. "
                "\"이번 주 평일 저녁이랑 주말 낮 중에 뭐가 더 편해? 맞으면 가볍게 밥 먹자\"처럼 두 옵션만 주세요."
            )
        case "generic":
            return _ko_generic_answer(context_hint, message)
        case unreachable:
            assert_never(unreachable)


def ko_suggestions(intent: CoachIntent) -> list[str]:
    match intent:
        case "bar_approach":
            return ["첫마디 더 자연스럽게", "거절 반응이면 어떻게?", "웃으면 다음 멘트"]
        case "old_crush_drinks":
            return ["더 짧게 줄여줘", "답 오면 다음 문장", "부담 덜한 버전"]
        case "coffee_approach":
            return ["정확히 말할 첫마디", "상대가 웃으면 다음엔?", "더 캐주얼하게"]
        case "slow_reply":
            return ["보낼 문장 하나만", "더 쿨하게 바꿔줘", "기다리는 기준 알려줘"]
        case "first_contact":
            return ["선톡 문장 써줘", "안 부담스럽게", "답 오면 이어가기"]
        case "blind_date":
            return ["소개팅 전 문자", "더 설레게", "약속 확인용으로 짧게"]
        case "after_date":
            return ["짧은 후속 문자", "더 플러팅하게", "너무 들이대지 않게"]
        case "profile_compliment":
            return ["사진 칭찬 문장", "외모 말고 분위기로", "답 오면 이어가기"]
        case "texting_pace":
            return ["연락 텀 문장", "서운함 덜 보이게", "상대가 느리면?"]
        case "confession_timing":
            return ["고백 문장 써줘", "타이밍 체크리스트", "부담 덜한 고백"]
        case "low_pressure_flirt":
            return ["가벼운 플러팅 3개", "더 장난스럽게", "선 넘지 않게"]
        case "meetup":
            return ["약속 제안 문장", "날짜 선택지 만들기", "거절당하면 답장"]
        case "generic":
            return ["바로 보낼 문장", "상대 반응별로 연습", "더 자연스럽게"]
        case unreachable:
            assert_never(unreachable)


def _ko_generic_answer(context_hint: str, message: str) -> str:
    topic = message.strip(" ?!.。！？")[:18] or "그 상황"
    return (
        f"{context_hint}지금은 긴 분석보다 바로 쓸 수 있는 문장 하나를 잡는 게 좋아요. "
        f"\"그 얘기 들으니까 궁금해졌어. 편할 때 조금만 더 들려줘\"처럼 부드럽게 열고, "
        f"{topic} 얘기가 돌아오면 거기서 구체적으로 받아주세요."
    )


def _mentions(message: str, needles: tuple[str, ...]) -> bool:
    return any(needle in message for needle in needles)
