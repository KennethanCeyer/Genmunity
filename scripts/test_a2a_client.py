#!/usr/bin/env python3
"""Standalone A2A (Agent2Agent) verification script.

Tests Agent Card discovery (`/.well-known/agent-card.json`) and JSON-RPC 2.0 `message/send`
communication with our GDG/GDE Community Hub Agent across all 3 data domains:
1. DevFest Community Hub + internal Google Slides
2. Build with AI Community Hub + Google Slides (`1CiGLGl91Nh_6kZOxeoHcH9hblmdx2Rt0oF5qX6jjEwE`)
3. Korean GDG/GDE Organizer Google Sheets (`146hMwkpdORd9njiWo2Yg6yZ7X40igZ3EiIk_kO0PJ34`)
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from community_hub_agent.a2a_server import a2a_app


async def verify_a2a_communication() -> None:
    transport = httpx.ASGITransport(app=a2a_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://localhost:8001"
    ) as client:
        # 1. Discover Agent Card
        card_resp = await client.get("/.well-known/agent-card.json")
        card_resp.raise_for_status()
        card = card_resp.json()
        print("=== 1. A2A Agent Card Discovered (/.well-known/agent-card.json) ===")
        print(f"Agent Name : {card['name']}")
        print(f"Protocol   : A2A v{card['protocolVersion']}")
        print(
            f"Skills     : {[s['id'] for s in card.get('skills', [])]}\n"
        )

        # 2. Send A2A JSON-RPC 2.0 Queries across Vector RAG, GraphRAG, and Hybrid Workflows
        sample_queries = [
            # Vector RAG (Document / Slide / Guideline)
            "DevFest 준비 타임라인과 공식 로고/네이밍 표기 규칙을 슬라이드 기준으로 알려줘.",
            # GraphRAG (Multi-hop Entity & Network Traversal)
            "박제창(PARK JAICHANG) 오거나이저가 운영 및 연사로 참여한 행사와 소속 챕터 관계망을 알려줘.",
            # Hybrid Vector RAG + GraphRAG (Co-hosting Network + Campaign Guideline/Policy)
            "GDG Incheon과 공동 주최한 챕터 관계망을 찾고 Build with AI 슬라이드 가이드라인과 정산 규정도 함께 알려줘.",
        ]

        for idx, query in enumerate(sample_queries, start=1):
            rpc_payload = {
                "jsonrpc": "2.0",
                "id": f"req-00{idx}",
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "messageId": f"msg-00{idx}",
                        "parts": [{"kind": "text", "text": query}],
                    }
                },
            }
            resp = await client.post("/", json=rpc_payload)
            resp.raise_for_status()
            data = resp.json()
            result = data["result"]
            text_part = result["parts"][0]["text"]
            data_part = result["parts"][1]["data"]
            print(f"=== 2-{idx}. A2A JSON-RPC Query: '{query}' ===")
            print(f"Selected Strategy : {data_part.get('routing', {}).get('strategy')}")
            print(text_part[:550] + ("...\n" if len(text_part) > 550 else "\n"))
            print(
                "Citations:",
                json.dumps(data_part["citations"][:2], ensure_ascii=False),
            )
            print(
                "Graph Triples (Top 2):",
                json.dumps(data_part.get("graph_triples", [])[:2], ensure_ascii=False),
                "\n",
            )


if __name__ == "__main__":
    asyncio.run(verify_a2a_communication())
