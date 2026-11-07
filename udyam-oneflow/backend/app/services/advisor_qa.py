"""Follow-up questions in the advisor chat: why, how much, what if, remove.

Every answer is computed from the catalogue and the rules engine (never the LLM),
so prices and eligibility in a reply are always exact. Works fully offline.
"""
from __future__ import annotations

import re

from app.schemas import BusinessProfile
from app.services import bundler, catalogue, eligibility, pricing, unlock
from app.services.segmenter import infer_segment, resolve_tier

WHY = re.compile(r"ஏன்|\bwhy\b|\bexplain\b|\bkyun\b|\bkyon\b|क्यों|क्यूँ|ஏன்", re.I)
PRICE = re.compile(r"how much|\bprice\b|\bcost\b|\brate\b|\bcharges?\b|kitna|kitne|kitni|कितना|कितने|कीमत|எவ்வளவு|விலை", re.I)
WHAT_IF = re.compile(r"what if|\bif i (?:had|have|get|got)\b|\bif we (?:had|have|get)\b|agar|अगर|suppose", re.I)
REMOVE = re.compile(r"நீக்கு|வேண்டாம்|\b(remove|drop|delete|cancel|no need (?:for|of)|don'?t want|do not want|don'?t need|"
                    r"hata(?:o|do|a)?|nahi chahiye|mat (?:do|chahiye))\b|हटा|नहीं चाहिए", re.I)
DESCRIBE = re.compile(r"what is|what's|what does|kya hai|क्या है", re.I)

T = {
    "en": {
        "price_line": "{name}: {lo}–{hi} {unit}/month. You pay {p12} on a 12-month term, {p24} on 24 months.",
        "setup": " One-time setup {setup} {unit}.",
        "no_setup": " No setup fee.",
        "min_contract": " Minimum contract {m} months.",
        "available": " ✓ Available for your business.",
        "in_plan": " It's already in your {rung} plan ({qty} × {p} = {total}/month).",
        "plan_total": "Your plans: Start {s}/month, Grow {g}/month, Complete {c}/month (12-month term).",
        "why_head": "Why this plan for a {seg} business in {city}:",
        "why_item": "• {name}: {why}",
        "why_ratio": "Start is {ratio}× what you pay today.",
        "why_rules": "Every item passed the checks for your city, team size and GST status. Prices come from the catalogue.",
        "no_plan_yet": "I'll explain as soon as I have your plan. ",
        "gst_have": "You already have an active GSTIN, so nothing more unlocks with GST.",
        "gst_unlock": "With an active GSTIN you'd unlock: {items}. A partner can help you register.",
        "gst_none": "A GSTIN wouldn't change your current plan; none of the products you need require it.",
        "gst_lose": "Without a GSTIN you couldn't buy: {items}. The rest of your plan still works (Start {s}/month).",
        "whatif_num": "With {what}, your Start plan would be {s1}/month (now {s0}) and Complete {c1}/month (now {c0}).",
        "whatif_unlock": " It would also unlock: {items}.",
        "term24": "On a 24-month term every line drops to the bottom of its price band: Start {s}/month instead of {s0}.",
        "removed": "Done: removed {items}. Your Start plan is now {s}/month.",
        "cant_remove": "{base} can't come out while {why} is in your plan: {why} needs a base internet connection. Say 'remove {why}' to drop both.",
        "nothing_removed": "That isn't in your plan right now.",
        "not_found": "I couldn't tell which product you mean. Try a name like 'Fibre 300', 'CCTV' or 'WhatsApp API'.",
    },
    "hi": {
        "price_line": "{name}: {lo}–{hi} {unit}/महीना। 12 महीने के कॉन्ट्रैक्ट पर {p12}, 24 महीने पर {p24}।",
        "setup": " एक बार का सेटअप {setup} {unit}।",
        "no_setup": " कोई सेटअप फ़ीस नहीं।",
        "min_contract": " न्यूनतम कॉन्ट्रैक्ट {m} महीने।",
        "available": " ✓ आपके व्यवसाय के लिए उपलब्ध।",
        "in_plan": " यह आपके {rung} प्लान में पहले से है ({qty} × {p} = {total}/महीना)।",
        "plan_total": "आपके प्लान: Start {s}/महीना, Grow {g}/महीना, Complete {c}/महीना (12 महीने)।",
        "why_head": "{city} में {seg} व्यवसाय के लिए यह प्लान क्यों:",
        "why_item": "• {name}: {why}",
        "why_ratio": "Start आपके मौजूदा खर्च का {ratio}× है।",
        "why_rules": "हर प्रोडक्ट आपके शहर, टीम और GST की जाँच में पास है। कीमतें कैटलॉग से हैं।",
        "no_plan_yet": "प्लान बनते ही मैं समझा दूँगा। ",
        "gst_have": "आपके पास पहले से सक्रिय GSTIN है, GST से और कुछ अनलॉक नहीं होगा।",
        "gst_unlock": "सक्रिय GSTIN से ये अनलॉक होंगे: {items}। पार्टनर रजिस्ट्रेशन में मदद कर सकते हैं।",
        "gst_none": "GSTIN से आपका मौजूदा प्लान नहीं बदलेगा।",
        "gst_lose": "GSTIN के बिना ये नहीं ले पाएँगे: {items}। बाकी प्लान चलेगा (Start {s}/महीना)।",
        "whatif_num": "{what} होने पर Start प्लान {s1}/महीना होगा (अभी {s0}) और Complete {c1}/महीना (अभी {c0})।",
        "whatif_unlock": " इससे ये भी अनलॉक होंगे: {items}।",
        "term24": "24 महीने पर हर लाइन सबसे कम कीमत पर आ जाती है: Start {s}/महीना (अभी {s0})।",
        "removed": "हो गया: {items} हटा दिया। अब Start प्लान {s}/महीना है।",
        "cant_remove": "{why} प्लान में रहते {base} नहीं हट सकता, क्योंकि {why} को इंटरनेट चाहिए। दोनों हटाने के लिए 'remove {why}' लिखें।",
        "nothing_removed": "यह अभी आपके प्लान में नहीं है।",
        "not_found": "किस प्रोडक्ट की बात है, समझ नहीं आया। जैसे 'Fibre 300', 'CCTV' या 'WhatsApp API' लिखें।",
    },
}
SEG_NAME = {"en": {"micro": "micro retail", "prof": "professional", "multi": "multi-site", "mfg": "manufacturing"},
            "hi": {"micro": "छोटी दुकान", "prof": "प्रोफ़ेशनल", "multi": "मल्टी-ब्रांच", "mfg": "मैन्युफ़ैक्चरिंग"}}


def _t(lang: str) -> dict:
    return T.get(lang, T["en"])


def rupees(v: int) -> str:
    from app.services.advisor import rupees as fmt

    return fmt(v)


def _unit(product, lang: str) -> str:
    unit = product.unit.replace("per ", "")
    return {"hi": f"प्रति {unit}", "ta": f"ஒரு {unit}க்கு"}.get(lang, f"per {unit}")


def mentioned(text: str, profile: BusinessProfile) -> tuple[list[str], list[str]]:
    """(product ids, need names) the message refers to."""
    from app.services.advisor import NEED_KEYWORDS, PRODUCT_ALIASES, _has_word

    low = f" {text.lower()} "
    pids: list[str] = []
    for pattern, pid in PRODUCT_ALIASES:
        if re.search(pattern, low) and pid not in pids:
            pids.append(pid)
    for p in catalogue.all_products():
        base = p.name.lower().split("(")[0].strip()
        if base in low and p.id not in pids:
            pids.append(p.id)
    needs = [n for n, words in NEED_KEYWORDS.items() if any(_has_word(low, w) for w in words)]
    if "wifi" in needs and "internet" in needs and not re.search(r"internet|broadband|fib(?:re|er)", low):
        needs.remove("internet")
    return pids, needs


def _need_products(needs: list[str], profile: BusinessProfile, segment: str) -> list[str]:
    out = []
    for need in needs:
        if need == "internet":
            out.append(bundler.choose_connectivity(profile, segment))
        elif need == "mobile":
            out.append(bundler.choose_mobile(profile, segment))
        else:
            out.extend(bundler.NEED_PRODUCTS.get(need, []))
    return out


def detect(text: str) -> str | None:
    if REMOVE.search(text):
        return "remove"
    if WHAT_IF.search(text):
        return "whatif"
    if PRICE.search(text):
        return "price"
    if WHY.search(text):
        return "why"
    return None


def _resolved(profile: BusinessProfile) -> tuple[BusinessProfile, str]:
    segment = profile.segment or infer_segment(profile.business_type, profile.sites) or "micro"
    return profile.model_copy(update={"segment": segment, "city_tier": resolve_tier(profile)}), segment


def answer(kind: str, text: str, profile: BusinessProfile, lang: str) -> tuple[str | None, BusinessProfile | None]:
    """Returns (reply, updated profile or None). reply None = not a question we can answer."""
    t = _t(lang)
    prof, segment = _resolved(profile)
    ready = bool(prof.city and prof.business_type and prof.employees)
    rec = bundler.recommend(prof) if ready else None
    have_plan = bool(rec and rec.available and rec.ladder)
    pids, needs = mentioned(text, prof)

    if kind == "price":
        targets = pids or _need_products(needs, prof, segment)
        if not targets:
            if have_plan:
                s, g, c = (r.total_monthly for r in rec.ladder)
                return t["plan_total"].format(s=rupees(s), g=rupees(g), c=rupees(c)), None
            return None, None
        return " ".join(_price_line(pid, prof, rec, lang) for pid in targets[:3]), None

    if kind == "why":
        if not have_plan:
            return (t["no_plan_yet"] if ready else None), None
        start = rec.ladder[0]
        lines = [t["why_head"].format(seg=SEG_NAME.get(lang, SEG_NAME["en"]).get(segment, segment), city=prof.city)]
        for item in start.items:
            lines.append(t["why_item"].format(name=item.name, why=item.why.split(". ")[0]))
        if start.vs_current_spend:
            lines.append(t["why_ratio"].format(ratio=start.vs_current_spend))
        lines.append(t["why_rules"])
        for u in [u for u in rec.blocked if u.needed][:2]:
            lines.append(u.message)
        return "\n".join(lines), None

    if kind == "whatif":
        return _what_if(text, prof, rec, lang), None

    if kind == "remove":
        targets = set(pids) | set(_need_products(needs, prof, segment))
        if not targets and not needs:
            return t["not_found"], None
        drop_needs = set(needs)
        for pid in targets:
            p = catalogue.get(pid)
            if p and p.category == "Connectivity" and p.unit == "per site" and not p.requires_one_of:
                drop_needs.add("internet")
            elif pid in ("P07", "P08"):
                drop_needs.add("mobile")
            else:
                drop_needs.update(n for n, ids in bundler.NEED_PRODUCTS.items() if pid in ids)
        before = {i.product_id for i in rec.ladder[0].items} if have_plan else set()
        new_needs = [n for n in prof.needs if n not in drop_needs]
        new_req = [p for p in prof.requested_products if p not in targets]
        if new_needs == list(prof.needs) and new_req == list(prof.requested_products):
            return t["nothing_removed"], None
        updated = profile.model_copy(update={"needs": new_needs, "requested_products": new_req})
        rec2 = bundler.recommend(_resolved(updated)[0])
        if not (rec2.available and rec2.ladder):
            return t["nothing_removed"], None
        after = {i.product_id for i in rec2.ladder[0].items}
        kept = [a for a in rec2.trace.get("auto_added", []) if a["product"] in targets]
        gone = [catalogue.get(p).name for p in before - after]
        if not gone and kept:
            # e.g. "remove internet" while CCTV needs it: say so instead of pretending.
            why = kept[0]["reason"].split(" requires")[0]
            return t["cant_remove"].format(base=kept[0]["name"], why=why), None
        gone = gone or [catalogue.get(p).name for p in targets if catalogue.get(p)]
        return t["removed"].format(items=", ".join(gone), s=rupees(rec2.ladder[0].total_monthly)), updated
    return None, None


def _price_line(pid: str, prof: BusinessProfile, rec, lang: str) -> str:
    t = _t(lang)
    p = catalogue.get(pid)
    unit = _unit(p, lang)
    line = t["price_line"].format(name=p.name, lo=rupees(p.price_min), hi=rupees(p.price_max), unit=unit,
                                  p12=rupees(pricing.unit_price(p, 12)), p24=rupees(pricing.unit_price(p, 24)))
    line += t["setup"].format(setup=rupees(p.setup), unit=unit) if p.setup else t["no_setup"]
    if p.min_contract > 12:
        line += t["min_contract"].format(m=p.min_contract)
    if prof.city and resolve_tier(prof) is not None:
        res = eligibility.check(p, prof, resolve_tier(prof))
        if res["failed"]:
            line += " " + unlock.build(p, res, prof, resolve_tier(prof)).message
        else:
            line += t["available"]
            if rec and rec.available and prof.needs:
                for rung in rec.ladder:
                    item = next((i for i in rung.items if i.product_id == pid), None)
                    if item:
                        line += t["in_plan"].format(rung=rung.label, qty=item.qty, p=rupees(item.unit_price),
                                                    total=rupees(item.unit_price * item.qty))
                        break
    return line


def _what_if(text: str, prof: BusinessProfile, rec, lang: str) -> str | None:
    t = _t(lang)
    low = text.lower()
    if not (rec and rec.available and rec.ladder):
        return None
    s0, c0 = rec.ladder[0].total_monthly, rec.ladder[2].total_monthly

    if re.search(r"gst", low):
        negative = re.search(r"\b(no|not|don'?t|without|lose|cancel\w*|nahi)\b", low)
        if negative and prof.has_gstin:
            alt = prof.model_copy(update={"has_gstin": False, "gstin_status": None, "gstin": None})
            rec2 = bundler.recommend(alt)
            lost = [u for u in rec2.blocked if u.blocked_by.startswith("gstin")
                    and u.product_id not in {b.product_id for b in rec.blocked}]
            if not lost:
                return t["gst_none"]
            items = ", ".join(u.name for u in lost)
            return t["gst_lose"].format(items=items, s=rupees(rec2.ladder[0].total_monthly))
        if prof.has_gstin and (prof.gstin_status or "Active") == "Active":
            return t["gst_have"]
        alt = prof.model_copy(update={"has_gstin": True, "gstin_status": "Active"})
        rec2 = bundler.recommend(alt)
        now_blocked = {u.product_id for u in rec.blocked if u.blocked_by.startswith("gstin")}
        unlocked = [u for u in rec.blocked if u.product_id in now_blocked
                    and u.product_id not in {b.product_id for b in rec2.blocked}]
        if not unlocked:
            return t["gst_none"]
        items = ", ".join(f"{u.name} ({rupees(u.adds_per_month[0])}–{rupees(u.adds_per_month[1])}/mo)" for u in unlocked)
        return t["gst_unlock"].format(items=items)

    if re.search(r"24|two year|2 year|do saal", low):
        rec2 = bundler.recommend(prof, 24)
        return t["term24"].format(s=rupees(rec2.ladder[0].total_monthly), s0=rupees(s0))

    from app.services.advisor import NUM, _num

    update, what = {}, None
    m = re.search(NUM + r"\s*(?:staff|employees|people|log|लोग|workers)", low)
    if m:
        update["employees"], what = _num(m.group(1)), m.group(0)
    m = re.search(NUM + r"\s*(?:sites|branches|locations|outlets|stores|shops|शाखा)", low)
    if m:
        update["sites"], what = _num(m.group(1)), (what + ", " if what else "") + m.group(0)
    if not update:
        return None
    alt = prof.model_copy(update={**update, "segment": None})
    alt = alt.model_copy(update={"segment": infer_segment(alt.business_type, alt.sites)})
    rec2 = bundler.recommend(alt)
    if not (rec2.available and rec2.ladder):
        return None
    reply = t["whatif_num"].format(what=what, s1=rupees(rec2.ladder[0].total_monthly), s0=rupees(s0),
                                   c1=rupees(rec2.ladder[2].total_monthly), c0=rupees(c0))
    newly = [u for u in rec.blocked if u.product_id not in {b.product_id for b in rec2.blocked}]
    if newly:
        reply += t["whatif_unlock"].format(items=", ".join(u.name for u in newly[:4]))
    return reply


T['ta'] = {'price_line': '{name}: மாதம் {lo}–{hi} {unit}. 12 மாத ஒப்பந்தத்தில் {p12}, 24 மாதத்தில் {p24}.', 'setup': ' ஒருமுறை அமைப்புக் கட்டணம் {setup} {unit}.', 'no_setup': ' அமைப்புக் கட்டணம் இல்லை.', 'min_contract': ' குறைந்தபட்ச ஒப்பந்தம் {m} மாதங்கள்.', 'available': ' ✓ உங்கள் தொழிலுக்குக் கிடைக்கும்.', 'in_plan': ' இது ஏற்கனவே உங்கள் {rung} திட்டத்தில் உள்ளது ({qty} × {p} = மாதம் {total}).', 'plan_total': 'உங்கள் திட்டங்கள்: Start மாதம் {s}, Grow மாதம் {g}, Complete மாதம் {c} (12 மாதம்).', 'why_head': '{city}-இல் உள்ள {seg} தொழிலுக்கு இந்தத் திட்டம் ஏன்:', 'why_item': '• {name}: {why}', 'why_ratio': 'Start இன்றைய செலவின் {ratio}× ஆகும்.', 'why_rules': 'ஒவ்வொரு தயாரிப்பும் உங்கள் நகரம், குழு அளவு மற்றும் GST சரிபார்ப்புகளில் தேர்ச்சி பெற்றது. விலைகள் பட்டியலிலிருந்து.', 'no_plan_yet': 'திட்டம் தயாரானதும் விளக்குகிறேன். ', 'gst_have': 'உங்களிடம் ஏற்கனவே செயலில் உள்ள GSTIN உள்ளது; GST மூலம் மேலும் எதுவும் திறக்காது.', 'gst_unlock': 'செயலில் உள்ள GSTIN இருந்தால் இவை திறக்கும்: {items}. பதிவு செய்ய பார்ட்னர் உதவுவார்.', 'gst_none': 'GSTIN உங்கள் தற்போதைய திட்டத்தை மாற்றாது.', 'gst_lose': 'GSTIN இல்லாமல் இவற்றை வாங்க முடியாது: {items}. மீதி திட்டம் தொடரும் (Start மாதம் {s}).', 'whatif_num': '{what} இருந்தால் Start மாதம் {s1} (இப்போது {s0}), Complete மாதம் {c1} (இப்போது {c0}).', 'whatif_unlock': ' இவையும் திறக்கும்: {items}.', 'term24': '24 மாத ஒப்பந்தத்தில் ஒவ்வொரு வரியும் குறைந்த விலைக்கு வரும்: Start மாதம் {s} (இப்போது {s0}).', 'removed': 'சரி: {items} நீக்கப்பட்டது. இப்போது Start மாதம் {s}.', 'cant_remove': "{why} திட்டத்தில் இருக்கும் வரை {base}-ஐ நீக்க முடியாது: {why}-க்கு இணைய இணைப்பு தேவை. இரண்டையும் நீக்க 'remove {why}' என்று எழுதுங்கள்.", 'nothing_removed': 'அது இப்போது உங்கள் திட்டத்தில் இல்லை.', 'not_found': "எந்தத் தயாரிப்பைச் சொல்கிறீர்கள் என்று புரியவில்லை. 'Fibre 300', 'CCTV' அல்லது 'WhatsApp API' என்று எழுதுங்கள்."}
SEG_NAME['ta'] = {'micro': 'சிறு கடை', 'prof': 'தொழில்முறை', 'multi': 'பல கிளை', 'mfg': 'உற்பத்தி'}
