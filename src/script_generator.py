import json
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass

import anthropic
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TOPIC_POOLS = {
    "motivation": [
        "포기하고 싶을 때", "새벽에 일어나는 힘", "실패 후 다시 일어서기",
        "작은 습관의 힘", "성공한 사람들의 공통점", "지금 시작해야 하는 이유",
        "꿈을 이루는 사람의 특징", "자신감을 키우는 방법", "멘탈 관리법",
        "1%의 성장", "불편한 것을 견디는 힘", "목표를 이루는 비결",
        "남들이 쉴 때 나는", "변화를 두려워하지 마라", "오늘이 가장 빠른 날",
        "후회 없는 삶", "운은 노력하는 자에게", "마인드셋의 차이",
        "시간의 소중함", "자기 자신을 믿어라", "끈기의 힘",
        "평범함에서 벗어나기", "당신의 한계는 착각이다", "작게 시작하라",
        "매일 조금씩", "실패는 성공의 어머니", "도전하는 용기",
        "집중력을 높이는 법", "나를 바꾸는 첫걸음", "결과보다 과정",
    ],
    "fun_facts": [
        "인체의 놀라운 비밀", "우주의 신비", "동물의 숨겨진 능력",
        "음식에 숨겨진 비밀", "수학의 재미있는 패턴", "역사 속 우연의 일치",
        "뇌과학의 놀라운 발견", "언어의 재미있는 기원", "기술의 숨겨진 역사",
        "지구의 놀라운 사실", "인간 심리의 비밀", "색깔의 숨겨진 의미",
        "수면의 과학", "물의 놀라운 성질", "시간에 대한 재미있는 사실",
        "DNA의 비밀", "바다의 미지의 세계", "냄새와 기억의 관계",
        "직감의 과학", "꿈에 대한 과학적 사실", "중력의 신비",
        "빛의 놀라운 성질", "소리의 과학", "미생물의 세계",
        "기후와 문명", "감정의 과학", "기억력의 비밀",
        "진화의 놀라운 사례", "확률의 역설", "착시의 과학",
    ],
    "life_tips": [
        "아침 루틴 최적화", "돈 모으는 습관", "시간 관리 꿀팁",
        "집중력 높이는 법", "스트레스 해소법", "수면 질 높이기",
        "효과적인 공부법", "인간관계 개선 팁", "건강한 식습관",
        "운동 시작하는 법", "절약하는 생활 습관", "정리정돈 꿀팁",
        "자기관리 루틴", "생산성 높이는 법", "독서 습관 만들기",
        "대화를 잘하는 법", "첫인상 좋게 만들기", "피부 관리 팁",
        "요리 초보 꿀팁", "옷 잘 입는 법", "면접 잘 보는 법",
        "발표 잘하는 법", "기억력 높이는 법", "감정 조절하는 법",
        "습관 만드는 법", "스마트폰 활용 팁", "에너지 관리법",
        "목표 설정하는 법", "SNS 활용 팁", "자신감 키우는 법",
    ],
    "history": [
        "클레오파트라의 진짜 모습", "조선시대 과학 기술", "로마 멸망의 진짜 이유",
        "고대 이집트의 일상", "바이킹의 진짜 모습", "실크로드의 비밀",
        "세종대왕의 숨겨진 업적", "제2차 세계대전 비화", "고대 그리스 민주주의",
        "피라미드 건설의 비밀", "중세 기사의 실제 생활", "임진왜란 비화",
        "나폴레옹의 숨겨진 이야기", "고려시대 무역", "산업혁명의 시작",
        "아즈텍 문명의 비밀", "조선 궁궐의 비밀", "냉전시대 스파이 이야기",
        "고대 올림픽", "한글 창제의 비밀", "대항해시대",
        "삼국시대 전쟁 전략", "르네상스 예술가들", "독립운동 숨은 영웅",
        "고대 의학의 역사", "화폐의 역사", "전염병이 바꾼 역사",
        "발명가들의 실패담", "고대 무역로", "음식의 역사",
    ],
}


@dataclass
class Script:
    title: str
    script: str
    tags: list[str]
    description: str
    category: str
    topic: str


class ScriptGenerator:
    def __init__(self, config: dict):
        self.config = config
        self.client = anthropic.Anthropic()
        self.template_env = Environment(
            loader=FileSystemLoader(Path(__file__).parent.parent / "templates")
        )
        self._used_topics: dict[str, set] = {k: set() for k in TOPIC_POOLS}

    def _pick_topic(self, category: str) -> str:
        pool = TOPIC_POOLS.get(category, TOPIC_POOLS["motivation"])
        available = [t for t in pool if t not in self._used_topics[category]]
        if not available:
            self._used_topics[category].clear()
            available = pool
        topic = available[0]
        self._used_topics[category].add(topic)
        return topic

    def _render_prompt(self, category: str, topic: str) -> str:
        template = self.template_env.get_template(f"{category}.j2")
        return template.render(topic=topic)

    async def generate_one(self, category: str) -> Script:
        topic = self._pick_topic(category)
        prompt = self._render_prompt(category, topic)
        llm_cfg = self.config["llm"]

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.messages.create(
                model=llm_cfg["model"],
                max_tokens=llm_cfg["max_tokens"],
                messages=[{"role": "user", "content": prompt}],
            ),
        )

        text = response.content[0].text
        start = text.find("{")
        end = text.rfind("}") + 1
        data = json.loads(text[start:end])

        return Script(
            title=data["title"],
            script=data["script"],
            tags=data.get("tags", []),
            description=data.get("description", ""),
            category=category,
            topic=topic,
        )

    async def generate_batch(self, category: str, count: int) -> list[Script]:
        semaphore = asyncio.Semaphore(5)

        async def _limited():
            async with semaphore:
                return await self.generate_one(category)

        tasks = [_limited() for _ in range(count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        scripts = []
        for r in results:
            if isinstance(r, Script):
                scripts.append(r)
            else:
                logger.error("Script generation failed: %s", r)
        return scripts
