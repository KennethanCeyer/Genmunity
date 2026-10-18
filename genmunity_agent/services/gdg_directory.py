from typing import Dict, Any, List, Optional

# ---------------------------------------------------------------------------
# GDE (Google Developer Experts) Directory (Allowed Screenshot Emails Only)
# ---------------------------------------------------------------------------
GDG_KOREA_GDE_DIRECTORY: List[Dict[str, Any]] = [
    {
        "team": "1팀",
        "category": "GDE",
        "is_gde": True,
        "domain": "AI",
        "name_en": "",
        "name": "",
        "slack_id": "",
        "affiliation": "",
        "email": "inureyes@gmail.com",
        "role": "AI GDE",
    },
    {
        "team": "1팀",
        "category": "GDE",
        "is_gde": True,
        "domain": "AI / Cloud / Go",
        "name_en": "Sungmin Han",
        "name": "한성민",
        "slack_id": "Sungmin Han",
        "affiliation": "IBM Korea Confluent",
        "email": "sniper45han@gmail.com",
        "role": "AI GDE",
    },
    {
        "team": "1팀",
        "category": "GDE",
        "is_gde": True,
        "domain": "Flutter",
        "name_en": "Dreamwalker (Jechang Park)",
        "name": "박제창",
        "slack_id": "Dreamwalker",
        "affiliation": "드림어스컴퍼니",
        "email": "aristojeff@gmail.com",
        "role": "Flutter GDE",
    },
]

# ---------------------------------------------------------------------------
# GDG Korea Chapter Directory (Allowed Screenshot Emails Only, PII Removed)
# ---------------------------------------------------------------------------
GDG_KOREA_CHAPTER_ORGANIZERS: List[Dict[str, Any]] = [
    # 2팀
    {"team": "2팀", "category": "GDG", "chapter": "GDG Incheon", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "jeongjoo.front@gmail.com"},
    {"team": "2팀", "category": "GDG", "chapter": "GDG Incheon", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "jonghoon.1738@gmail.com"},
    {"team": "2팀", "category": "GDG", "chapter": "GDG Busan", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "132262b@gmail.com"},
    {"team": "2팀", "category": "GDG", "chapter": "GDG Busan", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "toosky650@gmail.com"},
    # 3팀
    {"team": "3팀", "category": "GDG", "chapter": "GDG Pangyo", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "jinnya8166@gmail.com"},
    {"team": "3팀", "category": "GDG", "chapter": "GDG Cloud Korea", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "dntndus9611@gmail.com"},
    {"team": "3팀", "category": "GDG", "chapter": "GDG Busan", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "liza09201025@gmail.com"},
    {"team": "3팀", "category": "GDG", "chapter": "GDG Busan", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "noa9925@gmail.com"},
    # 4팀
    {"team": "4팀", "category": "GDG", "chapter": "GDG Busan", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "sgd0947@gmail.com"},
    {"team": "4팀", "category": "GDG", "chapter": "GDG Golang Korea", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "a24746440@gmail.com"},
    {"team": "4팀", "category": "GDG", "chapter": "GDG Campus Korea", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "bigdarkgold@gmail.com"},
    {"team": "4팀", "category": "GDG", "chapter": "GDG Campus Korea", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "bianbbc87@gmail.com"},
    # 5팀
    {"team": "5팀", "category": "GDG", "chapter": "GDG Golang Korea", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "jqyu.lee@gmail.com"},
    {"team": "5팀", "category": "GDG", "chapter": "GDG Incheon", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "kasseyy719@gmail.com"},
    {"team": "5팀", "category": "GDG", "chapter": "GDG Incheon", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "chochoq.dev@gmail.com"},
    {"team": "5팀", "category": "GDG", "chapter": "GDG Incheon", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "andkspark@gmail.com"},
    # 6팀
    {"team": "6팀", "category": "GDG", "chapter": "GDG Incheon", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "vnycall74@naver.com"},
    {"team": "6팀", "category": "GDG", "chapter": "GDG Incheon", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "dayeon.dev@gmail.com"},
    {"team": "6팀", "category": "GDG", "chapter": "GDG Seoul", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "cdypro0510@gmail.com"},
    {"team": "6팀", "category": "GDG", "chapter": "GDG Seoul", "name_en": "", "name": "", "slack_id": "", "field": "", "affiliation": "", "email": "nana.nykim@gmail.com"},
]

ALLOWED_GDG_GDE_EMAILS: List[str] = [
    entry["email"]
    for entry in (GDG_KOREA_GDE_DIRECTORY + GDG_KOREA_CHAPTER_ORGANIZERS)
    if entry.get("email")
]


def mask_email(email: str) -> str:
    """Mask personal email address to protect PII when needed."""
    if not email or "@" not in email:
        return "(이메일 미등록)"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    elif len(local) <= 5:
        masked_local = local[:2] + "***"
    else:
        masked_local = local[:2] + "****" + local[-2:]
    return f"{masked_local}@{domain}"


def is_gde_email(email: str) -> bool:
    """Return True if the email belongs to a verified Google Developer Expert (GDE)."""
    target = (email or "").strip().lower()
    if not target:
        return False
    return any(g["email"].lower() == target for g in GDG_KOREA_GDE_DIRECTORY if g.get("email"))


def find_exact_gdg_or_gde_member(
    email: Optional[str] = None,
    name: Optional[str] = None,
    slack_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Find a GDE or an allowed GDG Korea Chapter member by email, or (for developers) name/Slack ID.
    Prioritizes GDE directory entries first.
    """
    email_q = (email or "").strip().lower()
    name_q = (name or "").strip().lower()
    slack_q = (slack_id or "").strip().lower()

    for gde in GDG_KOREA_GDE_DIRECTORY:
        if email_q and gde["email"].lower() == email_q:
            return {**gde, "match_type": "GDE_EXACT", "speaker_email_eligible": True}
        if name_q and (
            (gde.get("name") and gde["name"].lower() == name_q)
            or (gde.get("name_en") and gde["name_en"].lower() == name_q)
        ):
            return {**gde, "match_type": "GDE_EXACT", "speaker_email_eligible": True}
        if slack_q and gde.get("slack_id") and gde["slack_id"].lower() == slack_q:
            return {**gde, "match_type": "GDE_EXACT", "speaker_email_eligible": True}

    for org in GDG_KOREA_CHAPTER_ORGANIZERS:
        if not org.get("email"):
            continue
        if email_q and org["email"].lower() == email_q:
            return {
                **org,
                "category": "GDG_CHAPTER_EXACT",
                "is_gde": is_gde_email(org["email"]),
                "match_type": "GDG_EXACT",
                "speaker_email_eligible": True,
            }
        if name_q and (
            (org.get("name") and org["name"].lower() == name_q)
            or (org.get("name_en") and org["name_en"].lower() == name_q)
        ):
            return {
                **org,
                "category": "GDG_CHAPTER_EXACT",
                "is_gde": is_gde_email(org["email"]),
                "match_type": "GDG_EXACT",
                "speaker_email_eligible": True,
            }
        if slack_q and org.get("slack_id") and org["slack_id"].lower() == slack_q:
            return {
                **org,
                "category": "GDG_CHAPTER_EXACT",
                "is_gde": is_gde_email(org["email"]),
                "match_type": "GDG_EXACT",
                "speaker_email_eligible": True,
            }

    return None


def validate_speaker_email_recipient(
    email: str,
    name: str = "",
    require_gde_or_exact_gdg: bool = True,
) -> Dict[str, Any]:
    """
    Enforce email allowlist policy:
    Speaker/community emails may ONLY be sent to the 23 allowed GDE/GDG emails from the roster.
    """
    clean_email = (email or "").strip().lower()
    if not clean_email or "@" not in clean_email:
        return {
            "allowed": False,
            "reason": "유효한 이메일 주소가 아닙니다.",
            "match_type": None,
        }

    # Check GDE directory first
    for gde in GDG_KOREA_GDE_DIRECTORY:
        if gde["email"].lower() == clean_email:
            label = gde["name"] or gde["email"]
            return {
                "allowed": True,
                "match_type": "GDE",
                "member": gde,
                "reason": f"검증된 {gde['role']} ({label}) 대상자입니다.",
            }

    # Check allowed GDG Chapter email list
    for org in GDG_KOREA_CHAPTER_ORGANIZERS:
        if org.get("email", "").lower() == clean_email:
            if (
                name
                and name.strip()
                and org.get("name")
                and name.strip().lower()
                not in (
                    org["name"].lower(),
                    org.get("name_en", "").lower(),
                )
            ):
                continue
            label = org.get("name") or org["email"]
            return {
                "allowed": True,
                "match_type": "GDG_EXACT_MATCH",
                "member": org,
                "reason": f"허용된 {org['chapter']} 소속 ({label}) 이메일입니다.",
            }

    if not require_gde_or_exact_gdg:
        return {"allowed": True, "match_type": "CUSTOM", "reason": "수동 지정 수신자"}

    return {
        "allowed": False,
        "match_type": None,
        "reason": (
            f"개인정보 보호 정책에 의해 발송 차단됨 ({mask_email(clean_email)}): "
            "지정된 GDG/GDE 허용 이메일 목록(23개)에 포함된 대상자에게만 발송할 수 있습니다."
        ),
    }


def search_gdg_gde_directory(
    query: str = "",
    only_gde: bool = False,
    unmask_exact_matches: bool = True,
) -> Dict[str, Any]:
    """
    Search the allowed 23 GDE/GDG emails (1팀~6팀).
    Personal information (names, affiliations, Slack IDs) is removed for all members
    except the project developers (sniper45han@gmail.com, aristojeff@gmail.com / Dreamwalker).
    """
    q = (query or "").strip().lower()
    tokens = [t for t in q.replace(",", " ").split() if len(t) >= 2]

    gde_results: List[Dict[str, Any]] = []
    for gde in GDG_KOREA_GDE_DIRECTORY:
        haystack = (
            f"{gde.get('team', '')} {gde['domain']} {gde['name']} {gde['name_en']} "
            f"{gde['slack_id']} {gde['affiliation']} {gde['role']} {gde['email']}"
        ).lower()
        matched = (not q) or (q in haystack) or any(tok in haystack for tok in tokens)
        if matched:
            entry = dict(gde)
            entry["masked_email"] = mask_email(gde["email"])
            entry["email"] = gde["email"] if unmask_exact_matches else mask_email(gde["email"])
            entry["exact_match"] = True
            entry["speaker_email_eligible"] = True
            gde_results.append(entry)

    gdg_exact_matches: List[Dict[str, Any]] = []
    gdg_partial_matches: List[Dict[str, Any]] = []

    if not only_gde:
        for org in GDG_KOREA_CHAPTER_ORGANIZERS:
            haystack = (
                f"{org.get('team', '')} {org['chapter']} {org['name']} {org['name_en']} "
                f"{org['slack_id']} {org['field']} {org['affiliation']} {org['email']}"
            ).lower()
            matched = (not q) or (q in haystack) or any(tok in haystack for tok in tokens)
            if not matched:
                continue

            entry = dict(org)
            raw_email = org.get("email", "")
            entry["masked_email"] = mask_email(raw_email)
            entry["is_gde"] = is_gde_email(raw_email)
            entry["exact_match"] = True
            entry["speaker_email_eligible"] = bool(raw_email)
            entry["email"] = raw_email if (unmask_exact_matches and raw_email) else mask_email(raw_email)
            gdg_exact_matches.append(entry)

    return {
        "query": query,
        "privacy_policy": (
            "개인정보 보호 정책 적용됨: 지정된 23개 GDG/GDE 이메일(1팀~6팀)만 사용하며, "
            "개발자(sniper45han@gmail.com, aristojeff@gmail.com / Dreamwalker) 외 나머지 인원의 개인정보(이름, 소속, 슬랙ID 등)는 모두 삭제되었습니다."
        ),
        "total_gde_count": len(GDG_KOREA_GDE_DIRECTORY),
        "total_gdg_chapter_members": len(GDG_KOREA_CHAPTER_ORGANIZERS),
        "allowed_emails": ALLOWED_GDG_GDE_EMAILS,
        "gde_matches": gde_results,
        "gdg_exact_matches": gdg_exact_matches,
        "gdg_masked_directory": gdg_partial_matches,
    }

