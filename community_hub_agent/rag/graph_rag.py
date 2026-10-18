"""Knowledge Graph & GraphRAG Engine for GDG/GDE Community Hub & Korean Organizer Data.

Constructs a multi-relational property graph (`networkx.MultiDiGraph` persisted to JSON,
with optional GCP Spanner Graph / Neo4j export) from:
1. Korean GDG/GDE Organizer & Event Excel/Sheets (`[External] GDG KR Communication.xlsx`)
2. DevFest & Build with AI Community Hub pages
3. Embedded Google Slides decks

Supports:
- Bilingual Entity Resolution (Korean <-> English organizer/speaker names & chapter aliases)
- Multi-hop Ego-Graph Traversal (1~3 hops)
- Shortest Path / Co-Hosting Network Analysis (`CO_HOSTED_WITH`)
- Relational Aggregations (Chapter -> Organizer -> Event -> Speaker/GDE -> Venue -> Topic)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx

from community_hub_agent.config import settings
from community_hub_agent.ingestion.models import (
    HubPageDocument,
    SheetDocument,
    SlackChannelDocument,
    SlideDeckDocument,
)

logger = logging.getLogger(__name__)


# Canonical chapter alias mapping (Korean/English/Abbreviated -> Canonical Chapter ID)
CHAPTER_ALIASES: dict[str, str] = {
    "gdg seoul": "GDG Seoul",
    "gdg 서울": "GDG Seoul",
    "seoul": "GDG Seoul",
    "gdg incheon": "GDG Incheon",
    "gdg 인천": "GDG Incheon",
    "incheon": "GDG Incheon",
    "gdg songdo": "GDG Songdo",
    "gdg 송도": "GDG Songdo",
    "songdo": "GDG Songdo",
    "gdg busan": "GDG Busan",
    "gdb busan": "GDG Busan",
    "gdg 부산": "GDG Busan",
    "busan": "GDG Busan",
    "gdg cloud busan": "GDG Cloud Busan",
    "cloud busan": "GDG Cloud Busan",
    "gdg daegu": "GDG Daegu",
    "gdg 대구": "GDG Daegu",
    "daegu": "GDG Daegu",
    "gdg daejeon": "GDG Daejeon",
    "gdg 대전": "GDG Daejeon",
    "daejeon": "GDG Daejeon",
    "gdg jeju": "GDG Jeju",
    "gdg 제주": "GDG Jeju",
    "jeju": "GDG Jeju",
    "gdg pangyo": "GDG Pangyo",
    "gdg 판교": "GDG Pangyo",
    "pangyo": "GDG Pangyo",
    "gdg campus korea": "GDG Campus Korea",
    "gdg 캠퍼스": "GDG Campus Korea",
    "gdg android korea": "GDG Android Korea",
    "gdg korea android": "GDG Android Korea",
    "gdg 안드로이드": "GDG Android Korea",
    "android korea": "GDG Android Korea",
    "gdg cloud korea": "GDG Cloud Korea",
    "gdg cloud": "GDG Cloud Korea",
    "cloud": "GDG Cloud Korea",
    "gdg golang korea": "GDG Golang Korea",
    "gdg golang": "GDG Golang Korea",
    "gdg 고랭": "GDG Golang Korea",
    "golang korea": "GDG Golang Korea",
    "flutter seoul": "Flutter Seoul",
    "gdgoc inha": "GDGoC Inha",
    "gdsc inha": "GDGoC Inha",
    "inha": "GDGoC Inha",
    "gdgoc sogang": "GDGoC Sogang",
    "gdgoc yonsei": "GDGoC Yonsei",
    "yonsei": "GDGoC Yonsei",
    "gdgoc ewha": "GDGoC Ewha",
    "ewha": "GDGoC Ewha",
    "gdgoc dongguk": "GDGoC Dongguk",
    "gdgoc donguk": "GDGoC Dongguk",
    "donguk": "GDGoC Dongguk",
    "gdgoc sookmyung": "GDGoC Sookmyung",
    "sookmyung": "GDGoC Sookmyung",
    "gdgoc konkuk": "GDGoC Konkuk",
    "gdsc konkuk": "GDGoC Konkuk",
    "konkuk": "GDGoC Konkuk",
    "gdsc soongsil": "GDSC Soongsil",
    "soongsil": "GDSC Soongsil",
    "gdsc sahmyook": "GDSC Sahmyook",
    "sahmyook": "GDSC Sahmyook",
}

# Bilingual Person Entity Resolution Map:
# Maps English Name (from `26 Active Rate`) and Korean Name (from event tabs) -> Canonical Person Label
BILINGUAL_PERSON_MAP: dict[str, tuple[str, list[str]]] = {
    # GDG Seoul
    "shinye song": ("송신예 (Shinye Song)", ["송신예", "Shinye Song"]),
    "송신예": ("송신예 (Shinye Song)", ["송신예", "Shinye Song"]),
    "dayoung cho": ("조다영 (Dayoung Cho)", ["조다영", "Dayoung Cho", "Dayoung  Cho"]),
    "조다영": ("조다영 (Dayoung Cho)", ["조다영", "Dayoung Cho"]),
    "nayeon kim": ("김나연 (Nayeon Kim)", ["김나연", "Nayeon Kim"]),
    "김나연": ("김나연 (Nayeon Kim)", ["김나연", "Nayeon Kim"]),
    "sungyun jo": ("조성윤 (SungYun Jo)", ["조성윤", "SungYun Jo"]),
    "조성윤": ("조성윤 (SungYun Jo)", ["조성윤", "SungYun Jo"]),
    "yoonsu kang": ("강윤수 (Yoonsu Kang)", ["강윤수", "Yoonsu Kang"]),
    "강윤수": ("강윤수 (Yoonsu Kang)", ["강윤수", "Yoonsu Kang"]),
    "giwon yun": ("윤지원 (Giwon Yun)", ["윤지원", "Giwon Yun"]),
    "윤지원": ("윤지원 (Giwon Yun)", ["윤지원", "Giwon Yun"]),
    # GDG Android Korea
    "kyeongwan kang": ("강경완 (Kyeongwan Kang)", ["강경완", "Kyeongwan Kang"]),
    "강경완": ("강경완 (Kyeongwan Kang)", ["강경완", "Kyeongwan Kang"]),
    "taehwan kwon": ("권태환 (Taehwan Kwon)", ["권태환", "Taehwan Kwon"]),
    "권태환": ("권태환 (Taehwan Kwon)", ["권태환", "Taehwan Kwon"]),
    "pil ju bae": ("배필주 (Pil Ju Bae)", ["배필주", "Pil Ju Bae"]),
    "배필주": ("배필주 (Pil Ju Bae)", ["배필주", "Pil Ju Bae"]),
    "kimin ryu": ("류기민 (Kimin Ryu)", ["류기민", "Kimin Ryu"]),
    "류기민": ("류기민 (Kimin Ryu)", ["류기민", "Kimin Ryu"]),
    "suhyeon kim": ("김수현 (Suhyeon Kim)", ["김수현", "Suhyeon Kim"]),
    "김수현": ("김수현 (Suhyeon Kim)", ["김수현", "Suhyeon Kim"]),
    "hyunwoo lee": ("이현우 (Hyunwoo Lee)", ["이현우", "Hyunwoo Lee"]),
    "이현우": ("이현우 (Hyunwoo Lee)", ["이현우", "Hyunwoo Lee"]),
    # GDG Campus Korea
    "lee euisuk": ("이의석 (LEE EUISUK)", ["이의석", "LEE EUISUK"]),
    "이의석": ("이의석 (LEE EUISUK)", ["이의석", "LEE EUISUK"]),
    "kang inyeong": ("강인영 (Kang Inyeong)", ["강인영", "Kang Inyeong"]),
    "강인영": ("강인영 (Kang Inyeong)", ["강인영", "Kang Inyeong"]),
    "daehyun kim": ("김대현 (Daehyun Kim)", ["김대현", "Daehyun Kim"]),
    "김대현": ("김대현 (Daehyun Kim)", ["김대현", "Daehyun Kim"]),
    "eunji jung": ("정은지 (Eunji Jung)", ["정은지", "Eunji Jung"]),
    "정은지": ("정은지 (Eunji Jung)", ["정은지", "Eunji Jung"]),
    "subin kim": ("김수빈 (Subin Kim)", ["김수빈", "Subin Kim"]),
    "김수빈": ("김수빈 (Subin Kim)", ["김수빈", "Subin Kim"]),
    "hyeonseo youn": ("윤현서 (Hyeonseo Youn)", ["윤현서", "Hyeonseo Youn"]),
    "윤현서": ("윤현서 (Hyeonseo Youn)", ["윤현서", "Hyeonseo Youn"]),
    "heesoo ra": ("라희수 (Heesoo Ra)", ["라희수", "Heesoo Ra"]),
    "라희수": ("라희수 (Heesoo Ra)", ["라희수", "Heesoo Ra"]),
    # GDG Cloud Korea
    "hyeonji jeong": ("정현지 (Hyeonji Jeong)", ["정현지", "Hyeonji Jeong"]),
    "정현지": ("정현지 (Hyeonji Jeong)", ["정현지", "Hyeonji Jeong"]),
    "choi chi young": ("최치영 (Choi Chi Young)", ["최치영", "Choi Chi Young"]),
    "최치영": ("최치영 (Choi Chi Young)", ["최치영", "Choi Chi Young"]),
    "suyeon woo": ("우수연 (Suyeon Woo)", ["우수연", "Suyeon Woo"]),
    "우수연": ("우수연 (Suyeon Woo)", ["우수연", "Suyeon Woo"]),
    "najin yang": ("양나진 (Najin Yang)", ["양나진", "Najin Yang"]),
    "양나진": ("양나진 (Najin Yang)", ["양나진", "Najin Yang"]),
    # GDG Golang Korea
    "sungmin han": ("한성민 (Sungmin Han)", ["한성민", "Sungmin Han"]),
    "한성민": ("한성민 (Sungmin Han)", ["한성민", "Sungmin Han"]),
    "park jaichang": ("박제창 (PARK JAICHANG)", ["박제창", "PARK JAICHANG"]),
    "박제창": ("박제창 (PARK JAICHANG)", ["박제창", "PARK JAICHANG"]),
    "jhin lee": ("이진 (Jhin Lee)", ["이진", "Jhin Lee"]),
    "hyunseo jung": ("정현서 (Hyunseo Jung)", ["정현서", "Hyunseo Jung"]),
    "정현서": ("정현서 (Hyunseo Jung)", ["정현서", "Hyunseo Jung"]),
    "jaegyu lee": ("이제규 (JaeGyu Lee)", ["이제규", "JaeGyu Lee"]),
    "이제규": ("이제규 (JaeGyu Lee)", ["이제규", "JaeGyu Lee"]),
    "wooseok han": ("한우석 (Wooseok Han)", ["한우석", "Wooseok Han"]),
    "uiseon yu": ("유의선 (Uiseon Yu)", ["유의선", "Uiseon Yu"]),
    # GDG Incheon / Songdo
    "hyeokjun kwon": ("권혁준 (Hyeokjun Kwon)", ["권혁준", "Hyeokjun Kwon"]),
    "권혁준": ("권혁준 (Hyeokjun Kwon)", ["권혁준", "Hyeokjun Kwon"]),
    "jeongjoo lee": ("이정주 (Jeongjoo Lee)", ["이정주", "Jeongjoo Lee"]),
    "이정주": ("이정주 (Jeongjoo Lee)", ["이정주", "Jeongjoo Lee"]),
    "seung shin ko": ("고승신 (Seung Shin Ko)", ["고승신", "Seung Shin Ko"]),
    "yoon changhyeon": ("윤창현 (Yoon Changhyeon)", ["윤창현", "Yoon Changhyeon"]),
    "jaebaek lee": ("이재백 (Jaebaek Lee)", ["이재백", "Jaebaek Lee"]),
    "sangjoon han": ("한상준 (Sangjoon Han)", ["한상준", "Sangjoon Han"]),
    "한상준": ("한상준 (Sangjoon Han)", ["한상준", "Sangjoon Han"]),
    "gwangmoo you": ("유광무 (GwangMoo You)", ["유광무", "GwangMoo You"]),
    "유광무": ("유광무 (GwangMoo You)", ["유광무", "GwangMoo You"]),
    "lee young bin": ("이영빈 (Lee Young Bin)", ["이영빈", "Lee Young Bin"]),
    "이영빈": ("이영빈 (Lee Young Bin)", ["이영빈", "Lee Young Bin"]),
    "sae byeok cho": ("조새벽 (sae byeok cho)", ["조새벽", "sae byeok cho"]),
    "조새벽": ("조새벽 (sae byeok cho)", ["조새벽", "sae byeok cho"]),
    "kim injae": ("김인재 (KIM INJAE)", ["김인재", "KIM INJAE"]),
    "maro kim": ("김마로 (Maro Kim)", ["김마로", "Maro Kim"]),
    "김마로": ("김마로 (Maro Kim)", ["김마로", "Maro Kim"]),
    "jonghoon lee": ("이종훈 (Jonghoon Lee)", ["이종훈", "Jonghoon Lee"]),
    "이종훈": ("이종훈 (Jonghoon Lee)", ["이종훈", "Jonghoon Lee"]),
    "go young min": ("고영민 (Go Young Min)", ["고영민", "Go Young Min"]),
    "고영민": ("고영민 (Go Young Min)", ["고영민", "Go Young Min"]),
    "daniel kim": ("Daniel Kim", ["Daniel Kim", "daniel kim"]),
    # GDG Pangyo
    "heeju jo": ("조희주 (heeju Jo)", ["조희주", "heeju Jo"]),
    "조희주": ("조희주 (heeju Jo)", ["조희주", "heeju Jo"]),
    "kevin jin": ("Kevin Jin", ["Kevin Jin"]),
    "eunjin ko": ("고은진 (Eunjin ko)", ["고은진", "Eunjin ko"]),
    "고은진": ("고은진 (Eunjin ko)", ["고은진", "Eunjin ko"]),
    # GDG Daejeon
    "inchul kim": ("김인철 (Inchul Kim)", ["김인철", "Inchul Kim"]),
    "김인철": ("김인철 (Inchul Kim)", ["김인철", "Inchul Kim"]),
    "seoboseok": ("서보석 (SeoBoseok)", ["서보석", "SeoBoseok"]),
    "서보석": ("서보석 (SeoBoseok)", ["서보석", "SeoBoseok"]),
    "jang jaewon": ("장재원 (Jang Jaewon)", ["장재원", "Jang Jaewon"]),
    "장재원": ("장재원 (Jang Jaewon)", ["장재원", "Jang Jaewon"]),
    # GDG Daegu
    "ga-in olivia choi": ("최가인 (Ga-in Olivia Choi)", ["최가인", "Ga-in Olivia Choi"]),
    "최가인": ("최가인 (Ga-in Olivia Choi)", ["최가인", "Ga-in Olivia Choi"]),
    "kim joonseok": ("김준석 (KIM JOONSEOK)", ["김준석", "KIM JOONSEOK"]),
    "김준석": ("김준석 (KIM JOONSEOK)", ["김준석", "KIM JOONSEOK"]),
    "jihyeon hwang": ("황지현 (JiHyeon Hwang)", ["황지현", "JiHyeon Hwang"]),
    "황지현": ("황지현 (JiHyeon Hwang)", ["황지현", "JiHyeon Hwang"]),
    # GDG Busan
    "gidong sung": ("성기동 (Gidong Sung)", ["성기동", "Gidong Sung"]),
    "성기동": ("성기동 (Gidong Sung)", ["성기동", "Gidong Sung"]),
    "jackie cheon": ("천명기 (jackie Cheon)", ["천명기", "jackie Cheon"]),
    "천명기": ("천명기 (jackie Cheon)", ["천명기", "jackie Cheon"]),
    "yejin seo": ("서예진 (YEJIN SEO)", ["서예진", "YEJIN SEO"]),
    "서예진": ("서예진 (YEJIN SEO)", ["서예진", "YEJIN SEO"]),
    "nam woojin": ("남우진 (Nam Woojin)", ["남우진", "Nam Woojin"]),
    "jaewang lee": ("이재왕 (JaeWang Lee)", ["이재왕", "JaeWang Lee"]),
    "이재왕": ("이재왕 (JaeWang Lee)", ["이재왕", "JaeWang Lee"]),
    "jang won seok": ("장원석 (Jang Won Seok)", ["장원석", "Jang Won Seok"]),
    # GDG Jeju
    "joon ho lee": ("이준호 (Joon Ho Lee)", ["이준호", "Joon Ho  Lee", "Joon Ho Lee"]),
    "leehojun": ("이호준 (leehojun)", ["이호준", "leehojun"]),
    "kim seung ju": ("김승주 (Kim Seung ju)", ["김승주", "Kim Seung ju"]),
    "wonbeom choi": ("최원범 (WonBeom Choi)", ["최원범", "WonBeom Choi"]),
    "park nuri": ("박누리 (Park Nuri)", ["박누리", "Park Nuri"]),
    "lee myungheon": ("이명헌 (Lee MyungHeon)", ["이명헌", "Lee MyungHeon"]),
    # Korean GDEs (from GDG_GDE_GDGoC List in Korea.xlsx & Event Speaker records)
    "hyeonseok noh": ("노현석 (HyeonSeok Noh)", ["노현석", "HyeonSeok Noh", "Pluu"]),
    "노현석": ("노현석 (HyeonSeok Noh)", ["노현석", "HyeonSeok Noh", "Pluu"]),
    "jaewoong eum": ("엄재웅 (Jaewoong Eum)", ["엄재웅", "Jaewoong Eum", "skydoves"]),
    "엄재웅": ("엄재웅 (Jaewoong Eum)", ["엄재웅", "Jaewoong Eum", "skydoves"]),
    "sungyong an": ("안성용 (Sungyong An)", ["안성용", "Sungyong An", "안성용(Soup)"]),
    "안성용": ("안성용 (Sungyong An)", ["안성용", "Sungyong An", "안성용(Soup)"]),
    "jeongkyu shin": ("신정규 (Jeongkyu Shin)", ["신정규", "Jeongkyu Shin"]),
    "신정규": ("신정규 (Jeongkyu Shin)", ["신정규", "Jeongkyu Shin"]),
    "chansung park": ("박찬성 (Chansung Park)", ["박찬성", "Chansung Park"]),
    "박찬성": ("박찬성 (Chansung Park)", ["박찬성", "Chansung Park"]),
    "kwon jeongmin": ("권정민 (Kwon JeongMin)", ["권정민", "Kwon JeongMin"]),
    "권정민": ("권정민 (Kwon JeongMin)", ["권정민", "Kwon JeongMin"]),
    "lee junbum": ("이준범 (Lee Junbum)", ["이준범", "Lee Junbum", "Beomi"]),
    "이준범": ("이준범 (Lee Junbum)", ["이준범", "Lee Junbum", "Beomi"]),
    "park haesun": ("박해선 (Park Haesun)", ["박해선", "Park Haesun"]),
    "박해선": ("박해선 (Park Haesun)", ["박해선", "Park Haesun"]),
    "minho ryu": ("류민호 (Minho Ryu)", ["류민호", "Minho Ryu"]),
    "류민호": ("류민호 (Minho Ryu)", ["류민호", "Minho Ryu"]),
    "jaeyeon baek": ("백재연 (Jaeyeon Baek)", ["백재연", "Jaeyeon Baek"]),
    "백재연": ("백재연 (Jaeyeon Baek)", ["백재연", "Jaeyeon Baek"]),
    "seungwoo lee": ("이성우 (Seungwoo Lee)", ["이성우", "Seungwoo Lee"]),
    "이성우": ("이성우 (Seungwoo Lee)", ["이성우", "Seungwoo Lee"]),
    "chiyoung choi": ("최치영 (Choi Chi Young)", ["최치영", "Choi Chi Young", "ChiYoung Choi"]),
    "seongyun byeon": ("변성윤 (Seongyun Byeon)", ["변성윤", "Seongyun Byeon", "카일"]),
    "변성윤": ("변성윤 (Seongyun Byeon)", ["변성윤", "Seongyun Byeon", "카일"]),
    "dreamwalker": ("박제창 (PARK JAICHANG)", ["박제창", "PARK JAICHANG", "Dreamwalker"]),
    # Slack #organizers (C04E1UAAY) Community Manager, Organizers, and Speakers
    "권나현": ("권나현 (Nahyun Kwon)", ["권나현", "Nahyun Kwon", "나현"]),
    "nahyun kwon": ("권나현 (Nahyun Kwon)", ["권나현", "Nahyun Kwon", "나현"]),
    "황재웅": ("황재웅 (Jaewoong Hwang)", ["황재웅", "Jaewoong Hwang"]),
    "jaewoong hwang": ("황재웅 (Jaewoong Hwang)", ["황재웅", "Jaewoong Hwang"]),
    "이재훈": ("이재훈 (Jaehun Lee)", ["이재훈", "Jaehun Lee"]),
    "jaehun lee": ("이재훈 (Jaehun Lee)", ["이재훈", "Jaehun Lee"]),
    "건주": ("건주 (Geonju)", ["건주", "Geonju"]),
    "geonju": ("건주 (Geonju)", ["건주", "Geonju"]),
    "권준호": ("권준호 (Junho Kwon)", ["권준호", "Junho Kwon"]),
    "junho kwon": ("권준호 (Junho Kwon)", ["권준호", "Junho Kwon"]),
    "이진석": ("이진석 (Jhinseok Lee)", ["이진석", "Jhinseok Lee", "jhin"]),
    "jhinseok lee": ("이진석 (Jhinseok Lee)", ["이진석", "Jhinseok Lee", "jhin"]),
    "정명훈": ("정명훈 (Myunghoon Jung)", ["정명훈", "Myunghoon Jung"]),
    "박진형": ("박진형 (Jinhyeong Park)", ["박진형", "Jinhyeong Park"]),
    "안영학": ("안영학 (Younghak Ahn)", ["안영학", "Younghak Ahn"]),
    "sasha denisov": ("Sasha Denisov", ["Sasha Denisov", "사샤 데니소프"]),
    "노경모": ("노경모 (Kyeongmo Noh)", ["노경모", "Kyeongmo Noh"]),
    "kyeongmo noh": ("노경모 (Kyeongmo Noh)", ["노경모", "Kyeongmo Noh"]),
    "권진겸": ("권진겸 (Jingyeom Kwon)", ["권진겸", "Jingyeom Kwon"]),
    "조은옥": ("조은옥 (Eunok Jo)", ["조은옥", "Eunok Jo", "Eunok"]),
    "eunok": ("조은옥 (Eunok Jo)", ["조은옥", "Eunok Jo", "Eunok"]),
    "신성진": ("신성진 (Sungjin Shin)", ["신성진", "Sungjin Shin"]),
    "송태웅": ("송태웅 (Taewoong Song)", ["송태웅", "Taewoong Song"]),
    "신관섭": ("신관섭 (Gwanseop Shin)", ["신관섭", "Gwanseop Shin"]),
    "정민석": ("정민석 (Minseok Jeong)", ["정민석", "Minseok Jeong"]),
    "신진규": ("신진규 (Jingyu Shin)", ["신진규", "Jingyu Shin"]),
}

TECH_TOPICS: dict[str, list[str]] = {
    "Gemini": ["gemini", "제미나이"],
    "Gemma": ["gemma", "젬마"],
    "Flutter": ["flutter", "플러터"],
    "Android / Compose": ["android", "안드로이드", "compose", "깜포즈"],
    "Google Cloud / Vertex AI": ["vertex", "cloud", "gcp", "클라우드"],
    "RAG / LLM": ["rag", "llm", "프롬프트", "prompt", "hallucination", "token"],
    "AI Agent / ADK / Antigravity": ["agent", "에이전트", "adk", "antigravity", "바이브코딩", "vibecoding"],
    "Golang": ["golang", "go to jeju", "고랭"],
    "JAX / Fine-tuning": ["jax", "파인튜닝", "sft", "dpo"],
    "Hackathon": ["해커톤", "hackathon"],
}


def resolve_person_name(raw_name: str) -> tuple[str, list[str]]:
    """Normalizes a person's name (Korean or English) to a canonical node label and alias list."""
    cleaned = re.sub(r"\s+", " ", raw_name).strip()
    key = cleaned.lower()
    if key in BILINGUAL_PERSON_MAP:
        return BILINGUAL_PERSON_MAP[key]
    return cleaned, [cleaned]


def extract_chapters_from_cell(raw_chapter_str: str) -> list[str]:
    """Extracts one or more canonical GDG/GDGoC chapters from a cell like 'GDG Cloud Korea X Seoul'."""
    if not raw_chapter_str:
        return []
    text = raw_chapter_str.replace("\n", " ").strip()
    if text == "GDG 독도":
        return []

    found: list[str] = []
    lower_text = text.lower()

    # First check multi-chapter delimiters: X, x, &, /, ,
    parts = re.split(r"\s+(?:[xX&/]|and)\s+|,\s*", text)
    for part in parts:
        p_clean = part.strip()
        if not p_clean:
            continue
        p_low = p_clean.lower()
        if p_low in CHAPTER_ALIASES:
            canon = CHAPTER_ALIASES[p_low]
            if canon not in found:
                found.append(canon)
            continue
        # Try prefixing 'gdg ' if it's a bare city/tech name in a multi-chapter list
        if f"gdg {p_low}" in CHAPTER_ALIASES:
            canon = CHAPTER_ALIASES[f"gdg {p_low}"]
            if canon not in found:
                found.append(canon)
            continue
        # Substring match against known chapter aliases
        matched = False
        for alias, canon in sorted(
            CHAPTER_ALIASES.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if len(alias) >= 4 and alias in p_low:
                if canon not in found:
                    found.append(canon)
                matched = True
        if not matched and ("gdg" in p_low or "gdsc" in p_low or "flutter" in p_low):
            if p_clean not in found:
                found.append(p_clean)

    if not found and lower_text in CHAPTER_ALIASES:
        found.append(CHAPTER_ALIASES[lower_text])
    return found


def infer_campaign_series(tab_name: str, title: str = "") -> str:
    """Infers the campaign series from the worksheet tab name or event title."""
    low = f"{tab_name} {title}".lower()
    if "devfest" in low:
        return "DevFest"
    if "ioex" in low or "i/o extended" in low:
        return "I/O Extended"
    if "bwai" in low or "build with ai" in low:
        return "Build with AI"
    if "dinner" in low or "회고" in low:
        return "Year-End Dinner"
    return "Community Event"


def infer_year(tab_name: str, date_str: str = "") -> str:
    """Infers the event year (2024, 2025, 2026) from tab name or date string."""
    if tab_name.startswith("26"):
        return "2026"
    if tab_name.startswith("25"):
        return "2025"
    if tab_name.startswith("24"):
        return "2024"
    for y in ("2026", "2025", "2024"):
        if y in date_str:
            return y
    return "2025"


@dataclass
class GraphSearchResult:
    """Structured result from a GraphRAG query."""

    query: str
    matched_entities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    multi_hop_paths: list[str] = field(default_factory=list)
    graph_analytics_summary: str = ""
    markdown_context: str = ""


class CommunityKnowledgeGraph:
    """Knowledge Graph & GraphRAG Retriever over GDG/GDE Chapters, Organizers, Speakers, Events, and Slides."""

    def __init__(self, graph_path: Path | None = None) -> None:
        self.graph_path = graph_path or settings.knowledge_graph_file
        self.graph = nx.MultiDiGraph()
        if self.graph_path.exists():
            self.load()

    def _upsert_node(
        self, node_id: str, entity_type: str, label: str, **attrs: Any
    ) -> None:
        """Inserts or merges attributes into a node in the MultiDiGraph."""
        if self.graph.has_node(node_id):
            existing = self.graph.nodes[node_id]
            # Merge roles or aliases sets if present
            for list_key in ("roles", "aliases", "campaigns", "years", "gde_categories"):
                if list_key in attrs:
                    prev_list = list(existing.get(list_key, []))
                    for item in attrs.pop(list_key):
                        if item and item not in prev_list:
                            prev_list.append(item)
                    existing[list_key] = prev_list
            for k, v in attrs.items():
                if v is not None and v != "":
                    existing[k] = v
        else:
            self.graph.add_node(
                node_id,
                entity_type=entity_type,
                label=label,
                **attrs,
            )

    def _add_edge(
        self, source: str, target: str, relation: str, **attrs: Any
    ) -> None:
        """Adds a directed edge if an identical relation between source and target doesn't already exist."""
        if self.graph.has_edge(source, target):
            for _, edge_data in self.graph[source][target].items():
                if edge_data.get("relation") == relation and edge_data.get(
                    "event_id"
                ) == attrs.get("event_id"):
                    return
        self.graph.add_edge(source, target, relation=relation, **attrs)

    def build_from_sources(
        self,
        sheet_docs: list[SheetDocument],
        slide_decks: list[SlideDeckDocument] | None = None,
        hub_pages: list[HubPageDocument] | None = None,
        slack_docs: list[SlackChannelDocument] | None = None,
    ) -> dict[str, int]:
        """Builds the complete Knowledge Graph from ingested Sheets/Excel, Slides, Hub pages, and Slack channels."""
        self.graph.clear()

        # 1. Seed CampaignSeries nodes
        for series in ("DevFest", "Build with AI", "I/O Extended", "Year-End Dinner", "Community Event"):
            self._upsert_node(
                f"series:{series}",
                entity_type="CampaignSeries",
                label=series,
                aliases=[series, series.lower()],
            )

        # 2. Process SheetDocuments (`[External] GDG KR Communication.xlsx` & `GDG_GDE_GDGoC List in Korea.xlsx`)
        for doc in sheet_docs:
            for row in doc.rows:
                tab = row.sheet_title
                vals = row.values

                if vals.get("구분"):
                    # Policy / Campaign Guideline node
                    policy_id = f"policy:{tab}"
                    self._upsert_node(
                        policy_id,
                        entity_type="CampaignPolicy",
                        label=f"{tab} {vals.get('구분', '운영 가이드')}",
                        campaign_tab=tab,
                        guidelines=vals.get("안내사항", ""),
                        source_url=doc.source_url,
                    )
                    series = infer_campaign_series(tab)
                    self._add_edge(
                        f"series:{series}",
                        policy_id,
                        relation="HAS_CAMPAIGN_POLICY",
                        tab=tab,
                    )
                    continue

                if tab == "26 Active Rate":
                    self._ingest_active_rate_row(vals)
                elif tab == "GDE":
                    self._ingest_gde_directory_row(vals)
                elif tab == "GDG":
                    self._ingest_gdg_directory_row(vals)
                elif tab == "GDGoC":
                    self._ingest_gdgoc_directory_row(vals)
                else:
                    self._ingest_event_row(tab, row.row_index, vals)

        # 3. Process SlideDeckDocuments
        for deck in slide_decks or []:
            deck_id = f"slide:{deck.presentation_id}"
            deck_cat = getattr(deck, "category", "general")
            series_label = (
                "Build with AI"
                if deck_cat == "build_with_ai" or "build with ai" in deck.title.lower()
                else "I/O Extended"
                if "i/o" in deck.title.lower() or "ioex" in deck.title.lower()
                else "DevFest"
            )
            slide_summaries = [
                f"[Slide {s.slide_number}] {s.title}"
                for s in deck.slides[:15]
                if s.title
            ]
            self._upsert_node(
                deck_id,
                entity_type="SlideDeck",
                label=deck.title,
                presentation_id=deck.presentation_id,
                source_url=deck.source_url,
                slide_count=len(deck.slides),
                slide_titles=slide_summaries,
            )
            self._add_edge(
                f"series:{series_label}",
                deck_id,
                relation="HAS_GUIDE_SLIDE",
                slide_count=len(deck.slides),
            )

        # 4. Process HubPageDocuments
        for page in hub_pages or []:
            page_cat = getattr(page, "category", "devfest")
            page_id = f"hub:{page_cat}"
            series_label = (
                "DevFest" if page_cat == "devfest" else "Build with AI"
            )
            headings = [
                sec.get("heading", "")
                for sec in getattr(page, "sections", [])
                if isinstance(sec, dict) and sec.get("heading")
            ]
            self._upsert_node(
                page_id,
                entity_type="CommunityHubPage",
                label=page.title,
                source_url=page.url,
                headings=headings[:15],
                discovered_slides=page.discovered_slide_urls,
            )
            self._add_edge(
                f"series:{series_label}",
                page_id,
                relation="HAS_HUB_PAGE",
                url=page.url,
            )

        # 5. Process SlackChannelDocuments (`#organizers` C04E1UAAY)
        for slack_doc in slack_docs or []:
            self._ingest_slack_channel(slack_doc)

        self.save()
        stats = self.get_stats()
        logger.info("Built Knowledge Graph: %s", stats)
        return stats

    def _ingest_slack_channel(self, slack_doc: SlackChannelDocument) -> None:
        """Ingests structured organizer announcements, new members, venues, and policies from Slack #organizers."""
        channel_node_id = f"slack:{slack_doc.channel_id}"
        self._upsert_node(
            channel_node_id,
            entity_type="SlackChannel",
            label=f"Slack #{slack_doc.channel_name} ({slack_doc.workspace_url})",
            channel_id=slack_doc.channel_id,
            source_url=slack_doc.source_url,
            thread_count=len(slack_doc.threads),
            aliases=[
                f"#{slack_doc.channel_name}",
                slack_doc.channel_name,
                slack_doc.channel_id,
                "슬랙",
                "오거나이저 슬랙",
                "slack",
            ],
        )

        # 1. Community Manager: 권나현 (Nahyun Kwon)
        cm_label, cm_aliases = resolve_person_name("권나현")
        cm_id = f"person:{cm_label}"
        self._upsert_node(
            cm_id,
            entity_type="Person",
            label=cm_label,
            roles=["Community Manager", "Googler"],
            aliases=cm_aliases + ["커뮤니티 매니저", "권나현 매니저"],
            affiliation="Google Developer Relations (KR Community Manager)",
            slack_id="U07N2A2C6F2",
        )
        self._add_edge(
            cm_id,
            channel_node_id,
            relation="MANAGES_CHANNEL",
            role="KR Community Manager",
        )

        # 2. Newly Joined Organizers announced in Slack #organizers
        new_organizers = [
            ("황재웅", "GDG Busan", "South", "U0987NJB139", "2026-08 신규 합류 (GDG Busan)"),
            ("이재훈", "GDG Busan", "South", "U098FNE4CF4", "2026-08 신규 합류 (GDG Busan)"),
            ("건주", "GDG Incheon", "West", "U09HC5SHSNZ", "2026-09 신규 합류 (GDG Incheon)"),
        ]
        for raw_name, chapter_name, region, slack_uid, note in new_organizers:
            canon_name, aliases = resolve_person_name(raw_name)
            pid = f"person:{canon_name}"
            ch_id = f"chapter:{chapter_name}"
            self._upsert_node(
                ch_id,
                entity_type="Chapter",
                label=chapter_name,
                region=region,
                aliases=[chapter_name],
            )
            self._upsert_node(
                pid,
                entity_type="Person",
                label=canon_name,
                roles=["Organizer"],
                primary_chapter=chapter_name,
                slack_id=slack_uid,
                aliases=aliases,
                note=note,
            )
            self._add_edge(
                pid,
                ch_id,
                relation="ORGANIZER_OF",
                source_tab="Slack #organizers",
                joined_note=note,
            )

        # 3. 2026 DevFest Sponsorship & Per-Attendee Budget Increase Policy (25,000 KRW)
        devfest_policy_id = "policy:2026_DevFest_Slack"
        self._upsert_node(
            devfest_policy_id,
            entity_type="CampaignPolicy",
            label="2026 DevFest 예산 증액 및 스폰서십 가이드 (1인당 25,000원 확대, AI Studio/Antigravity 추가 지원)",
            campaign_tab="Slack #organizers",
            guidelines=(
                "참석자 1인당 지원금 20,000원 → 25,000원 증액 확정, "
                "행사 최소 45일 전 신청 필수, 1개 챕터당 연 1회 DevFest만 지원, "
                "AI Studio / Antigravity 핸즈온 워크샵 포함 시 추가 예산 및 특별 SWAG 우대"
            ),
            source_url="https://gdgkr.slack.com/archives/C04E1UAAY/p1789610514705289",
            aliases=["2026 DevFest 예산", "25000원", "25,000원", "데브페스트 지원금"],
        )
        self._add_edge(
            "series:DevFest",
            devfest_policy_id,
            relation="HAS_CAMPAIGN_POLICY",
            year="2026",
            announced_by=cm_label,
        )

        # 4. 2026 Free Venue Support: 서울 AI 허브 (양재)
        venue_id = "venue:서울 AI 허브 (양재)"
        self._upsert_node(
            venue_id,
            entity_type="Venue",
            label="서울 AI 허브 (양재)",
            aliases=["서울 AI 허브", "양재 AI 허브", "무료 대관"],
            guidelines="2026 DevFest 및 커뮤니티 행사 무료 대관 공간 안내 (선착순 신청, 주차 불가/대중교통 권장, 케이터링/다과 반입 금지)",
            source_url="https://gdgkr.slack.com/archives/C04E1UAAY/p1783392528557949",
        )
        self._add_edge(
            channel_node_id,
            venue_id,
            relation="ANNOUNCED_FREE_VENUE",
            year="2026",
            announced_by=cm_label,
        )

        # 5. Key Slack-specific Events (2026 KR Developer Community Summit, GDG Incheon Agentathon, Google Cloud AI Builder Cup)
        summit_id = "event:Slack:2026_KR_Developer_Community_Summit"
        self._upsert_node(
            summit_id,
            entity_type="Event",
            label="[2026] KR Developer Community Summit (10/17~10/18, 리바이스 데님 자켓 웰컴 기프트)",
            title="2026 KR Developer Community Summit",
            campaign_series="Community Event",
            year="2026",
            date="2026-10-17 ~ 2026-10-18",
            venue="구글 스타트업 캠퍼스 (Google for Startups Campus Seoul)",
            aliases=["KR Developer Community Summit", "리바이스 데님 자켓", "데님 자켓", "오거나이저 서밋", "26-summit"],
            swag="리바이스 데님 자켓 (Levi's Denim Jacket - 참가 신청 오거나이저 대상 웰컴 기프트)",
        )
        self._add_edge(
            summit_id,
            "series:Community Event",
            relation="PART_OF_SERIES",
            year="2026",
        )

        agentathon_id = "event:Slack:2026_GDG_Incheon_Agentathon"
        self._upsert_node(
            agentathon_id,
            entity_type="Event",
            label="[2026] GDG Incheon Agentathon (에이전트톤 1조~7조 인천 로컬 AI 에이전트 웹서비스 배포)",
            title="GDG Incheon Agentathon",
            campaign_series="Build with AI",
            year="2026",
            date="2026-09-21",
            chapters=["GDG Incheon"],
            aliases=["Agentathon", "에이전트톤", "인천 에이전트톤"],
        )
        self._add_edge(
            "chapter:GDG Incheon",
            agentathon_id,
            relation="HOSTED_EVENT",
            year="2026",
            campaign="Build with AI",
            date="2026-09-21",
        )

        builder_cup_id = "event:Slack:2026_Google_Cloud_AI_Builder_Cup"
        self._upsert_node(
            builder_cup_id,
            entity_type="Event",
            label="[2026] Google Cloud AI Builder Cup (JAPAC 하이브리드 해커톤, 상금 $30,000+, 싱가포르 결선 지원)",
            title="Google Cloud AI Builder Cup",
            campaign_series="Build with AI",
            year="2026",
            date="2026",
            venue="Singapore",
            aliases=["Google Cloud AI Builder Cup", "AI Builder Cup", "싱가포르 해커톤"],
        )
        for applicant_name in ("김인철", "서보석", "윤지원", "조새벽", "변성윤"):
            app_canon, app_aliases = resolve_person_name(applicant_name)
            app_pid = f"person:{app_canon}"
            self._upsert_node(
                app_pid,
                entity_type="Person",
                label=app_canon,
                roles=["Organizer"],
                aliases=app_aliases,
            )
            self._add_edge(
                app_pid,
                builder_cup_id,
                relation="PARTICIPATED_AS_ORGANIZER",
                role="Priority Selection Applicant (Slack Thread Reply)",
                year="2026",
            )

        # 6. 2025 Build with AI Recommended Speakers from Pinned Notice
        bwai_speakers = [
            ("이준범", ["GDE", "Speaker"], "Gemma 2 모델을 한국어에 맞게 추가 튜닝하기"),
            ("박진형", ["Speaker"], "Gemini API를 활용한 웹 애플리케이션 개발 및 배포 (서울대)"),
            ("정명훈", ["GDE", "Speaker"], "Vertex AI Agent Builder / Gemini 2.0 Live API 실시간 영상 챗봇"),
            ("Sasha Denisov", ["GDE", "Speaker"], "Flutter + Firebase GenAI / flutter_gemma / Gemini Nano"),
            ("안영학", ["Speaker"], "이벤터스 대표 - AI로 행사 기획 및 운영 자동화하기 (300명 행사 1.8명 운영)"),
        ]
        for sp_raw, sp_roles, sp_topic in bwai_speakers:
            sp_canon, sp_aliases = resolve_person_name(sp_raw)
            sp_pid = f"person:{sp_canon}"
            self._upsert_node(
                sp_pid,
                entity_type="Person",
                label=sp_canon,
                roles=sp_roles,
                aliases=sp_aliases,
                recommended_topic=sp_topic,
            )
            self._add_edge(
                sp_pid,
                "series:Build with AI",
                relation="SPOKE_AT",
                session_info=f"[Slack 추천 연사] {sp_topic}",
                year="2025",
            )

    def _ingest_active_rate_row(self, vals: dict[str, str]) -> None:
        """Ingests a row from `26 Active Rate` linking Region <- Chapter <- Organizer."""
        raw_region = vals.get("Region", "").strip()
        raw_chapter = vals.get("GDG Chapter", "").strip()
        raw_name = vals.get("Name", "").strip()
        if not raw_name:
            return

        chapters = extract_chapters_from_cell(raw_chapter)
        chapter_name = chapters[0] if chapters else raw_chapter
        chapter_id = f"chapter:{chapter_name}"

        if chapter_name:
            self._upsert_node(
                chapter_id,
                entity_type="Chapter",
                label=chapter_name,
                region=raw_region,
                aliases=[chapter_name, raw_chapter],
            )
        if raw_region and chapter_name:
            region_id = f"region:{raw_region}"
            self._upsert_node(
                region_id,
                entity_type="Region",
                label=raw_region,
                aliases=[raw_region],
            )
            self._add_edge(
                chapter_id,
                region_id,
                relation="BELONGS_TO_REGION",
            )

        canon_name, aliases = resolve_person_name(raw_name)
        person_id = f"person:{canon_name}"
        self._upsert_node(
            person_id,
            entity_type="Person",
            label=canon_name,
            roles=["Organizer"],
            aliases=aliases,
            primary_chapter=chapter_name,
            region=raw_region,
            participation_score=vals.get("Participation", "0"),
            inactive_flag=vals.get("Inactive?", "0"),
        )
        if chapter_name:
            self._add_edge(
                person_id,
                chapter_id,
                relation="ORGANIZER_OF",
                region=raw_region,
                sheet="26 Active Rate",
            )

    def _ingest_gde_directory_row(self, vals: dict[str, str]) -> None:
        """Ingests a row from the `GDE` tab of `GDG_GDE_GDGoC List in Korea.xlsx`."""
        category = vals.get("분야", "").strip()
        eng_name = vals.get("Name", "").strip()
        kor_name = vals.get("이름", "").strip()
        slack_id = vals.get("GDG Korea 슬랙 ID", "").strip()
        affiliation = vals.get("소속", "").strip()
        email = vals.get("Email", "").strip()

        raw_name = kor_name or eng_name
        if not raw_name:
            return

        canon_name, aliases = resolve_person_name(raw_name)
        if kor_name and eng_name and canon_name == kor_name:
            canon_name = f"{kor_name} ({eng_name})"
        for a in (kor_name, eng_name, slack_id):
            if a and a not in aliases:
                aliases.append(a)

        person_id = f"person:{canon_name}"
        self._upsert_node(
            person_id,
            entity_type="Person",
            label=canon_name,
            roles=["GDE", "Speaker"],
            gde_categories=[category] if category else [],
            aliases=aliases,
            affiliation=affiliation,
            email=email,
            slack_id=slack_id,
        )

        # Link GDE -> Topic (EXPERT_IN_TOPIC)
        category_topic_map = {
            "AI": "Gemini",
            "Android": "Android / Compose",
            "Cloud": "Google Cloud / Vertex AI",
            "Go": "Golang",
            "Flutter": "Flutter",
            "Firebase": "Firebase",
        }
        if category:
            topic_label = category_topic_map.get(category, category)
            topic_id = f"topic:{topic_label}"
            self._upsert_node(
                topic_id,
                entity_type="Topic",
                label=topic_label,
                aliases=[topic_label, category, f"{category} GDE"],
            )
            self._add_edge(
                person_id,
                topic_id,
                relation="EXPERT_IN_TOPIC",
                gde_category=category,
                affiliation=affiliation,
                email=email,
            )

    def _ingest_gdg_directory_row(self, vals: dict[str, str]) -> None:
        """Ingests a row from the `GDG` tab of `GDG_GDE_GDGoC List in Korea.xlsx`."""
        raw_chapter = vals.get("Chapter", "").strip()
        eng_name = vals.get("Name", "").strip()
        kor_name = vals.get("이름", "").strip()
        slack_id = vals.get("GDG Korea 슬랙 ID", "").strip()
        job_field = vals.get("직무/분야", "").strip()
        affiliation = vals.get("소속", "").strip()
        email = vals.get("Email", "").strip()

        raw_name = kor_name or eng_name
        if not raw_name:
            return

        chapters = extract_chapters_from_cell(raw_chapter)
        chapter_name = chapters[0] if chapters else raw_chapter

        canon_name, aliases = resolve_person_name(raw_name)
        if kor_name and eng_name and canon_name == kor_name:
            canon_name = f"{kor_name} ({eng_name})"
        for a in (kor_name, eng_name, slack_id):
            if a and a not in aliases:
                aliases.append(a)

        person_id = f"person:{canon_name}"
        self._upsert_node(
            person_id,
            entity_type="Person",
            label=canon_name,
            roles=["Organizer"],
            aliases=aliases,
            primary_chapter=chapter_name,
            job_field=job_field,
            affiliation=affiliation,
            email=email,
            slack_id=slack_id,
        )

        if chapter_name:
            chapter_id = f"chapter:{chapter_name}"
            self._upsert_node(
                chapter_id,
                entity_type="Chapter",
                label=chapter_name,
                aliases=[chapter_name, raw_chapter],
            )
            self._add_edge(
                person_id,
                chapter_id,
                relation="ORGANIZER_OF",
                job_field=job_field,
                affiliation=affiliation,
                sheet="GDG Directory",
            )

    def _ingest_gdgoc_directory_row(self, vals: dict[str, str]) -> None:
        """Ingests active university lead rows (`26-27`, `25-26`) from `GDGoC` tab."""
        gdgoc_class = vals.get("Class", "").strip()
        # Focus graph nodes on current & recent cohorts (`26-27`, `25-26`) to keep graph high-signal
        if gdgoc_class not in ("26-27", "25-26"):
            return
        club_kor = vals.get("Club (KOR)", "").strip()
        club_eng = vals.get("Club (ENG)", "").strip()
        kor_name = vals.get("Name", "").strip()
        eng_name = vals.get("Name(ENG)", "").strip()
        email = vals.get("Email", "").strip()
        if not (club_kor and kor_name):
            return

        chapter_name = f"GDGoC {club_kor}"
        chapter_id = f"chapter:{chapter_name}"
        self._upsert_node(
            chapter_id,
            entity_type="Chapter",
            label=chapter_name,
            club_eng=club_eng,
            aliases=[chapter_name, club_kor, club_eng],
        )

        canon_name = f"{kor_name} ({eng_name})" if eng_name else kor_name
        person_id = f"person:{canon_name}"
        self._upsert_node(
            person_id,
            entity_type="Person",
            label=canon_name,
            roles=["GDGoC Lead"],
            aliases=[kor_name, eng_name] if eng_name else [kor_name],
            primary_chapter=chapter_name,
            cohort=gdgoc_class,
            email=email,
        )
        self._add_edge(
            person_id,
            chapter_id,
            relation="ORGANIZER_OF",
            cohort=gdgoc_class,
            sheet="GDGoC Directory",
        )

    def _ingest_event_row(
        self, tab: str, row_idx: int, vals: dict[str, str]
    ) -> None:
        """Ingests a chapter event row from 2024, 2025, or 2026 campaign worksheets."""
        raw_chapter = (
            vals.get("주최 GDG 챕터명")
            or vals.get("GDG Chapter")
            or vals.get("GDG chapter")
            or ""
        ).strip()
        if not raw_chapter:
            return

        chapters = extract_chapters_from_cell(raw_chapter)
        if not chapters:
            return

        date_str = (
            vals.get("행사 날짜")
            or vals.get("Date")
            or vals.get("연말 회고 디너 날짜")
            or ""
        ).strip()
        title = (
            vals.get("행사 타이틀")
            or vals.get("Title")
            or vals.get("[D-30] 🌟Bevy 이벤트 등록")
            or f"{tab} - {' & '.join(chapters)}"
        ).strip()
        if title.startswith("http"):
            title = f"{tab} - {' & '.join(chapters)}"

        venue = (
            vals.get("[D-40] 장소 대관 확정")
            or vals.get("장소")
            or vals.get("Venue")
            or vals.get("미팅 형태")
            or ""
        ).strip()
        event_format = (
            vals.get("이벤트 형식") or vals.get("미팅 형태") or ""
        ).strip()
        attendees = (
            vals.get("[D+1] 행사 전체 참석자 숫자")
            or vals.get("[D+1] 실참석자 숫자")
            or vals.get("실참석자 숫자(운영진, 스탭 포함 숫자) ex. 100(120)")
            or vals.get("실참석자 숫자(운영진, 스탭 포함 숫자) ex. 30(35)")
            or vals.get("# of Attendees")
            or vals.get("예상 참석자 숫자")
            or vals.get("예상 *핸즈온* 참석자 숫자")
            or vals.get("예상 전체 참석자 숫자")
            or vals.get("예상 규모 (참가자 숫자)")
            or vals.get("Request #credit (예상 참석자 숫자)")
            or ""
        ).strip()

        series = infer_campaign_series(tab, title)
        year = infer_year(tab, date_str)
        event_id = f"event:{tab}:R{row_idx}"

        self._upsert_node(
            event_id,
            entity_type="Event",
            label=f"[{tab}] {title} ({', '.join(chapters)})",
            title=title,
            campaign_tab=tab,
            campaign_series=series,
            year=year,
            date=date_str,
            chapters=chapters,
            venue=venue,
            event_format=event_format,
            attendees=attendees,
            raw_values=vals,
        )

        # Link Event -> CampaignSeries
        self._add_edge(
            event_id,
            f"series:{series}",
            relation="PART_OF_SERIES",
            year=year,
        )

        # Link Chapters -> Event and Co-hosting edges between Chapters
        for ch in chapters:
            ch_id = f"chapter:{ch}"
            self._upsert_node(
                ch_id,
                entity_type="Chapter",
                label=ch,
                aliases=[ch],
                campaigns=[series],
                years=[year],
            )
            self._add_edge(
                ch_id,
                event_id,
                relation="HOSTED_EVENT",
                year=year,
                campaign=series,
                date=date_str,
            )

        if len(chapters) > 1:
            for i in range(len(chapters)):
                for j in range(i + 1, len(chapters)):
                    ch_a = f"chapter:{chapters[i]}"
                    ch_b = f"chapter:{chapters[j]}"
                    self._add_edge(
                        ch_a,
                        ch_b,
                        relation="CO_HOSTED_WITH",
                        event_id=event_id,
                        event_title=title,
                        campaign=series,
                        year=year,
                    )
                    self._add_edge(
                        ch_b,
                        ch_a,
                        relation="CO_HOSTED_WITH",
                        event_id=event_id,
                        event_title=title,
                        campaign=series,
                        year=year,
                    )

        # Link Event -> Venue
        if venue and venue not in ("-", "대관한 장소 입력"):
            venue_id = f"venue:{venue}"
            self._upsert_node(
                venue_id,
                entity_type="Venue",
                label=venue,
                aliases=[venue],
            )
            self._add_edge(
                event_id,
                venue_id,
                relation="HELD_AT_VENUE",
                date=date_str,
            )

        # Extract participating organizers from 2026 campaign sheets
        org_str = vals.get("참여하는 GDG 운영진 이름 (','로 구분)", "").strip()
        if org_str:
            for raw_org in re.split(r"[,/]\s*", org_str):
                org_clean = raw_org.strip()
                if not org_clean or len(org_clean) < 2:
                    continue
                canon_name, aliases = resolve_person_name(org_clean)
                person_id = f"person:{canon_name}"
                self._upsert_node(
                    person_id,
                    entity_type="Person",
                    label=canon_name,
                    roles=["Organizer"],
                    aliases=aliases,
                    campaigns=[series],
                    years=[year],
                )
                self._add_edge(
                    person_id,
                    event_id,
                    relation="PARTICIPATED_AS_ORGANIZER",
                    campaign=series,
                    year=year,
                )
                for ch in chapters:
                    self._add_edge(
                        person_id,
                        f"chapter:{ch}",
                        relation="ORGANIZER_OF",
                        source_tab=tab,
                    )

        # Extract Speakers / GDEs / Googlers
        speaker_Texts = [
            vals.get("[D+1] 구글러/GDE 연사", ""),
            vals.get("연사 (구글러 혹은 GDE)", ""),
            vals.get("Googler speaker", ""),
            vals.get("Agenda & Speaker (Kor)", ""),
            vals.get("Note", ""),
        ]
        for sp_text in speaker_Texts:
            if sp_text and sp_text.strip() and sp_text.strip() != "-":
                self._extract_speakers_and_topics(
                    sp_text.strip(), event_id, chapters, series, year
                )

        # Also extract topics from title & summary
        topic_source = " ".join(
            [
                title,
                vals.get("주제(개요)", ""),
                vals.get("Agenda & Speaker (Kor)", ""),
            ]
        ).lower()
        for topic_label, keywords in TECH_TOPICS.items():
            if any(kw in topic_source for kw in keywords):
                topic_id = f"topic:{topic_label}"
                self._upsert_node(
                    topic_id,
                    entity_type="Topic",
                    label=topic_label,
                    aliases=[topic_label] + keywords,
                )
                self._add_edge(
                    event_id,
                    topic_id,
                    relation="COVERS_TOPIC",
                    year=year,
                )

    def _extract_speakers_and_topics(
        self,
        sp_text: str,
        event_id: str,
        chapters: list[str],
        series: str,
        year: str,
    ) -> None:
        """Extracts GDEs, Googlers, and community speakers from speaker/agenda cells."""
        lines = [ln.strip() for ln in sp_text.split("\n") if ln.strip()]
        for line in lines:
            if "===" in line or "코드랩 주제" in line:
                continue

            # Case 1: 'GDE: 한성민, 이준범, 박제창' or '구글러: David Mclau'
            if line.startswith("GDE:") or line.startswith("구글러:") or line.startswith("GDG -"):
                role_tag = (
                    "GDE"
                    if line.startswith("GDE:")
                    else "Googler"
                    if line.startswith("구글러:")
                    else "Speaker"
                )
                names_part = re.sub(r"^(?:GDE:|구글러:|GDG\s*-)\s*", "", line)
                for name_tok in re.split(r"[,/]\s*", names_part):
                    name_clean = name_tok.strip()
                    if not name_clean:
                        continue
                    self._link_speaker(
                        name_clean, [role_tag, "Speaker"], line, event_id, chapters, series, year
                    )
                continue

            # Case 2: '이영빈 (AI GDE)' or '박해선(AI, Cloud GDE)' or '이준범 (AI GDE)'
            m_paren = re.match(r"^([가-힣a-zA-Z\s]{2,20})\s*\(([^)]+)\)$", line)
            if m_paren:
                raw_name, role_desc = m_paren.group(1).strip(), m_paren.group(2).strip()
                roles = ["Speaker"]
                if "GDE" in role_desc.upper():
                    roles.append("GDE")
                self._link_speaker(
                    raw_name, roles, f"{raw_name} ({role_desc})", event_id, chapters, series, year
                )
                continue

            # Case 3: Agenda lines with '/' such as '세션 제목 / 박제창 / @Flutter Seoul, GDG Golang Korea'
            # or '신정규 / AI, ML GDE, Lablup 대표'
            if "/" in line:
                parts = [p.strip() for p in line.split("/") if p.strip()]
                for idx, part in enumerate(parts):
                    # Check if part looks like a Korean name (2~4 hangul chars, optionally with @affiliation)
                    name_part = part.split("@")[0].split(",")[0].strip()
                    if re.match(r"^[가-힣]{2,4}$", name_part):
                        roles = ["Speaker"]
                        if "GDE" in line.upper():
                            roles.append("GDE")
                        self._link_speaker(
                            name_part, roles, line, event_id, chapters, series, year
                        )
                continue

            # Case 4: English names list like 'Terry Chung Hwan Ahn Kyungpyo Park T Kim' or 'Jinwon Seo'
            en_names = re.findall(r"[A-Z][a-z]+(?:\s+\([A-Za-z]+\))?\s+[A-Z][a-z]+", line)
            if en_names:
                for en_name in en_names:
                    self._link_speaker(
                        en_name, ["Speaker", "Googler"], line, event_id, chapters, series, year
                    )
            elif len(line) <= 25 and re.match(r"^[가-힣a-zA-Z\s,]+$", line):
                for tok in line.split(","):
                    tok_clean = tok.strip()
                    if len(tok_clean) >= 2:
                        self._link_speaker(
                            tok_clean, ["Speaker"], line, event_id, chapters, series, year
                        )

    def _link_speaker(
        self,
        raw_name: str,
        roles: list[str],
        session_info: str,
        event_id: str,
        chapters: list[str],
        series: str,
        year: str,
    ) -> None:
        canon_name, aliases = resolve_person_name(raw_name)
        person_id = f"person:{canon_name}"
        self._upsert_node(
            person_id,
            entity_type="Person",
            label=canon_name,
            roles=roles,
            aliases=aliases,
            campaigns=[series],
            years=[year],
        )
        self._add_edge(
            person_id,
            event_id,
            relation="SPOKE_AT",
            roles=roles,
            session_info=session_info[:200],
            campaign=series,
            year=year,
        )

    def save(self) -> None:
        """Persists the MultiDiGraph to `data/knowledge_graph.json`."""
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self.graph)
        self.graph_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load(self) -> None:
        """Loads the MultiDiGraph from `data/knowledge_graph.json`."""
        if not self.graph_path.exists():
            return
        try:
            data = json.loads(self.graph_path.read_text(encoding="utf-8"))
            self.graph = nx.node_link_graph(data, directed=True, multigraph=True)
        except Exception as exc:
            logger.warning("Failed to load knowledge graph from %s: %s", self.graph_path, exc)

    def get_stats(self) -> dict[str, Any]:
        """Returns node and edge counts grouped by entity_type and relation."""
        node_types: dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            etype = data.get("entity_type", "Unknown")
            node_types[etype] = node_types.get(etype, 0) + 1

        edge_types: dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            rel = data.get("relation", "RELATED_TO")
            edge_types[rel] = edge_types.get(rel, 0) + 1

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": node_types,
            "edge_types": edge_types,
        }

    stats = get_stats


    def resolve_entities(self, query: str) -> list[str]:
        """Resolves query terms against graph node labels, bilingual aliases, and chapters."""
        q_low = query.lower().strip()
        q_tokens = [
            t
            for t in re.split(r"[\s,?/()]+", q_low)
            if len(t) >= 2 and t not in ("gdg", "gde", "행사", "운영진", "연사", "챕터", "알려줘", "누구", "어디")
        ]

        scored_nodes: list[tuple[float, str]] = []
        for node_id, data in self.graph.nodes(data=True):
            label = str(data.get("label", "")).lower()
            aliases = [str(a).lower() for a in data.get("aliases", [])]
            search_targets = [label] + aliases

            score = 0.0
            for target in search_targets:
                if not target:
                    continue
                if target in q_low:
                    score = max(score, 3.0 + len(target) * 0.1)
                for tok in q_tokens:
                    if tok == target:
                        score = max(score, 2.5)
                    elif len(tok) >= 2 and tok in target:
                        score = max(score, 1.5)

            if score > 0:
                scored_nodes.append((score, node_id))

        scored_nodes.sort(key=lambda x: x[0], reverse=True)
        return [nid for _, nid in scored_nodes[:10]]

    def query_subgraph(
        self,
        query: str,
        max_hops: int = 2,
        top_k: int = 20,
    ) -> GraphSearchResult:
        """Executes a GraphRAG retrieval over the Knowledge Graph.

        1. Resolves seed entities from the query (Chapters, Persons, Events, Venues, Topics, Series).
        2. Traverses k-hop undirected ego-neighborhoods around seed entities.
        3. Finds shortest connecting relational paths when 2+ entities are queried.
        4. Computes global/local graph analytics (co-hosting networks, GDE speakers, active organizers).
        """
        if self.graph.number_of_nodes() == 0 and self.graph_path.exists():
            self.load()

        seed_nodes = self.resolve_entities(query)
        undirected = self.graph.to_undirected()

        # Collect k-hop subgraph nodes and edges
        visited_nodes: set[str] = set(seed_nodes)
        for seed in seed_nodes[:5]:
            if seed in undirected:
                ego = nx.ego_graph(undirected, seed, radius=max_hops)
                visited_nodes.update(ego.nodes())

        q_low = query.lower()
        if any(k in q_low for k in ("연합", "공동", "co-host", "cohost", "함께")):
            for u, v, d in self.graph.edges(data=True):
                if d.get("relation") == "CO_HOSTED_WITH":
                    visited_nodes.add(u)
                    visited_nodes.add(v)
        if "gde" in q_low or "전문가" in q_low:
            for nid, nd in self.graph.nodes(data=True):
                if "GDE" in nd.get("roles", []):
                    visited_nodes.add(nid)
                    if nid in undirected:
                        visited_nodes.update(undirected.neighbors(nid))

        # Find multi-hop connecting paths between top seed entities
        multi_hop_paths: list[str] = []
        if len(seed_nodes) >= 2:
            for i in range(min(len(seed_nodes), 4)):
                for j in range(i + 1, min(len(seed_nodes), 4)):
                    src, dst = seed_nodes[i], seed_nodes[j]
                    if src in undirected and dst in undirected and nx.has_path(undirected, src, dst):
                        try:
                            path = nx.shortest_path(undirected, src, dst)
                            if 2 <= len(path) <= 5:
                                path_str = self._format_path(path)
                                if path_str not in multi_hop_paths:
                                    multi_hop_paths.append(path_str)
                        except Exception:
                            pass

        # Score and rank edges connected to seed_nodes first, then 2-hop edges
        ranked_edges: list[tuple[int, dict[str, Any]]] = []
        seen_edges: set[tuple[str, str, str]] = set()
        for u, v, data in self.graph.edges(data=True):
            if u not in visited_nodes and v not in visited_nodes:
                continue
            rel = data.get("relation", "RELATED_TO")
            edge_key = (u, v, rel)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            priority = 0
            if u in seed_nodes and v in seed_nodes:
                priority = 3
            elif u in seed_nodes or v in seed_nodes:
                priority = 2
            else:
                priority = 1

            # Boost edges matching query intent keywords
            q_low = query.lower()
            if ("연합" in q_low or "공동" in q_low or "함께" in q_low) and rel == "CO_HOSTED_WITH":
                priority += 3
            if ("연사" in q_low or "발표" in q_low or "gde" in q_low or "전문가" in q_low or "초청" in q_low) and rel in (
                "SPOKE_AT",
                "EXPERT_IN_TOPIC",
            ):
                priority += 3
            if ("운영진" in q_low or "오거나이저" in q_low or "리드" in q_low) and rel in (
                "ORGANIZER_OF",
                "PARTICIPATED_AS_ORGANIZER",
            ):
                priority += 3
            if ("장소" in q_low or "대관" in q_low or "어디" in q_low or "허브" in q_low or "권나현" in q_low) and rel in (
                "HELD_AT_VENUE",
                "ANNOUNCED_FREE_VENUE",
                "MANAGES_CHANNEL",
            ):
                priority += 3

            u_label = self.graph.nodes[u].get("label", u)
            v_label = self.graph.nodes[v].get("label", v)
            u_type = self.graph.nodes[u].get("entity_type", "")
            v_type = self.graph.nodes[v].get("entity_type", "")

            edge_record = {
                "source_id": u,
                "source_label": u_label,
                "source_type": u_type,
                "relation": rel,
                "target_id": v,
                "target_label": v_label,
                "target_type": v_type,
                "metadata": {
                    k: val
                    for k, val in data.items()
                    if k != "relation" and val is not None and val != ""
                },
            }
            ranked_edges.append((priority, edge_record))

        ranked_edges.sort(key=lambda x: x[0], reverse=True)
        # Ensure diversity across relation types within equal-priority tiers
        diversified: list[dict[str, Any]] = []
        overflow: list[dict[str, Any]] = []
        rel_counts: dict[str, int] = {}
        for _, edge_rec in ranked_edges:
            r_type = edge_rec["relation"]
            if rel_counts.get(r_type, 0) < 4:
                diversified.append(edge_rec)
                rel_counts[r_type] = rel_counts.get(r_type, 0) + 1
            else:
                overflow.append(edge_rec)
        top_relationships = (diversified + overflow)[:top_k]

        matched_entity_dicts: list[dict[str, Any]] = []
        for nid in seed_nodes:
            ndata = dict(self.graph.nodes[nid])
            ndata["node_id"] = nid
            matched_entity_dicts.append(ndata)

        analytics_summary = self._build_analytics_summary(query, seed_nodes)
        md_lines = ["### [GraphRAG Knowledge Graph Subgraph]"]
        if matched_entity_dicts:
            md_lines.append("\n#### 1. 매칭된 핵심 엔티티 (Seed Entities)")
            for ent in matched_entity_dicts[:8]:
                etype = ent.get("entity_type", "Entity")
                label = ent.get("label", ent["node_id"])
                extras = []
                for k in (
                    "roles",
                    "gde_categories",
                    "primary_chapter",
                    "affiliation",
                    "job_field",
                    "email",
                    "slack_id",
                    "region",
                    "date",
                    "venue",
                    "attendees",
                    "event_format",
                    "campaigns",
                ):
                    if ent.get(k):
                        extras.append(f"{k}={ent[k]}")
                extra_str = f" ({', '.join(extras)})" if extras else ""
                md_lines.append(f"- **[{etype}] {label}**{extra_str}")

        if multi_hop_paths:
            md_lines.append("\n#### 2. 엔티티 간 멀티홉 연결 경로 (Multi-Hop Relational Paths)")
            for p in multi_hop_paths[:6]:
                md_lines.append(f"- {p}")

        if top_relationships:
            md_lines.append("\n#### 3. 서브그래프 관계 트리플 (Knowledge Graph Triples)")
            for rel_item in top_relationships:
                meta_str = ""
                if rel_item["metadata"]:
                    compact_meta = ", ".join(
                        f"{k}={v}" for k, v in list(rel_item["metadata"].items())[:4]
                    )
                    meta_str = f" [{compact_meta}]"
                md_lines.append(
                    f"- ({rel_item['source_type']}: **{rel_item['source_label']}**) "
                    f"—[`{rel_item['relation']}`]→ "
                    f"({rel_item['target_type']}: **{rel_item['target_label']}**){meta_str}"
                )

        if analytics_summary:
            md_lines.append("\n#### 4. 그래프 구조 분석 요약 (Graph Analytics)")
            md_lines.append(analytics_summary)

        return GraphSearchResult(
            query=query,
            matched_entities=matched_entity_dicts,
            relationships=top_relationships,
            multi_hop_paths=multi_hop_paths,
            graph_analytics_summary=analytics_summary,
            markdown_context="\n".join(md_lines),
        )

    def _format_path(self, node_path: list[str]) -> str:
        """Formats a sequence of node IDs into a readable relational chain."""
        segments: list[str] = []
        for idx, nid in enumerate(node_path):
            label = self.graph.nodes[nid].get("label", nid)
            etype = self.graph.nodes[nid].get("entity_type", "")
            segments.append(f"**{label}** ({etype})")
            if idx + 1 < len(node_path):
                nxt = node_path[idx + 1]
                rel = "RELATED"
                if self.graph.has_edge(nid, nxt):
                    first_edge = next(iter(self.graph[nid][nxt].values()))
                    rel = first_edge.get("relation", "RELATED")
                elif self.graph.has_edge(nxt, nid):
                    first_edge = next(iter(self.graph[nxt][nid].values()))
                    rel = f"←{first_edge.get('relation', 'RELATED')}"
                segments.append(f"—[`{rel}`]—")
        return " ".join(segments)

    def _build_analytics_summary(self, query: str, seed_nodes: list[str]) -> str:
        """Builds global & entity-specific structural summaries from the graph."""
        lines: list[str] = []

        # 1. Co-hosting collaborations summary
        cohost_pairs: list[str] = []
        seen_pairs: set[tuple[str, str, str]] = set()
        for u, v, data in self.graph.edges(data=True):
            if data.get("relation") == "CO_HOSTED_WITH":
                pair = tuple(sorted([u, v])) + (str(data.get("event_id", "")),)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)  # type: ignore[arg-type]
                    u_lbl = self.graph.nodes[u].get("label", u)
                    v_lbl = self.graph.nodes[v].get("label", v)
                    ev_title = data.get("event_title", "")
                    yr = data.get("year", "")
                    cohost_pairs.append(f"{u_lbl} ✕ {v_lbl} ({yr} {ev_title})")
        if cohost_pairs:
            lines.append(
                f"- **챕터 간 공동 주최(Co-Hosted) 네트워크**: 총 {len(cohost_pairs)}건의 연합 관계 "
                f"({'; '.join(cohost_pairs[:8])})"
            )

        # 2. Multi-role people (Both Organizer and Speaker/GDE) & GDE directory
        dual_role_people: list[str] = []
        gde_speakers: list[str] = []
        for nid, data in self.graph.nodes(data=True):
            if data.get("entity_type") == "Person":
                roles = data.get("roles", [])
                lbl = data.get("label", nid)
                if "Organizer" in roles and "Speaker" in roles:
                    dual_role_people.append(
                        f"{lbl} ({', '.join(roles)}, 소속: {data.get('primary_chapter', 'GDG')})"
                    )
                if "GDE" in roles:
                    cats = ", ".join(data.get("gde_categories", [])) or "GDE"
                    aff = data.get("affiliation", "")
                    email = data.get("email", "")
                    detail = f"{lbl} [{cats}"
                    if aff:
                        detail += f" | {aff}"
                    if email:
                        detail += f" | {email}"
                    detail += "]"
                    gde_speakers.append(detail)
        if dual_role_people:
            lines.append(
                f"- **운영진이면서 연사(GDE/Speaker)로 활동한 인물**: {', '.join(dual_role_people[:10])}"
            )
        if gde_speakers:
            lines.append(
                f"- **국내 GDE 전문가 디렉토리 및 연사 목록 ({len(gde_speakers)}명)**: {'; '.join(gde_speakers[:18])}"
            )

        # 3. If a specific chapter is in seed_nodes, summarize its organizers, events, and venues
        for nid in seed_nodes[:3]:
            ndata = self.graph.nodes.get(nid, {})
            if ndata.get("entity_type") == "Chapter":
                ch_label = ndata.get("label", nid)
                orgs: list[str] = []
                events: list[str] = []
                cohosts: set[str] = set()
                for src, _, edata in self.graph.in_edges(nid, data=True):
                    if edata.get("relation") == "ORGANIZER_OF":
                        org_lbl = self.graph.nodes[src].get("label", src)
                        if org_lbl not in orgs:
                            orgs.append(org_lbl)
                for _, dst, edata in self.graph.out_edges(nid, data=True):
                    rel = edata.get("relation")
                    if rel == "HOSTED_EVENT":
                        ev_lbl = self.graph.nodes[dst].get("label", dst)
                        events.append(ev_lbl)
                    elif rel == "CO_HOSTED_WITH":
                        cohosts.add(self.graph.nodes[dst].get("label", dst))
                lines.append(
                    f"- **[{ch_label}] 챕터 그래프 요약**: 운영진 {len(orgs)}명 ({', '.join(orgs[:10])}), "
                    f"개최 이벤트 {len(events)}건 ({', '.join(events[:5])}), "
                    f"공동 주최 파트너 챕터: {', '.join(sorted(cohosts)) if cohosts else '단독 진행'}"
                )

        return "\n".join(lines)
