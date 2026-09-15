"""Deterministic, OCR-evidence-backed package declaration extraction.

This module deliberately does not guess.  A value is resolved only when its
printed label and its value are present in the same source image and close
enough to be part of the same declaration.  Every result keeps the actual OCR
words (including boxes and OCR variants) that supported it.
"""

from __future__ import annotations

import re

from rules_config import CONTACT, DATE, MANUFACTURER, QUANTITY


def _token(word: dict) -> str:
    return re.sub(r"[^a-z0-9₹]", "", word.get("text", "").lower())


def _nearby(left: dict, right: dict, horizontal: int = 520, vertical: int = 220) -> bool:
    return (
        left.get("image_id") == right.get("image_id")
        and abs((left["top"] + left["height"] / 2) - (right["top"] + right["height"] / 2)) <= vertical
        and abs((left["left"] + left["width"] / 2) - (right["left"] + right["width"] / 2)) <= horizontal
    )


def _provenance(words: list[dict]) -> list[dict]:
    """Copy only the evidence contract needed to trace a field reading."""
    return [{
        "text": word.get("text", ""), "confidence": round(float(word.get("conf", 0)), 1),
        "image_id": word.get("image_id", "image_01"),
        "source_filename": word.get("source_filename"), "ocr_variant": word.get("variant", "original"),
        "bbox": {key: word.get(key) for key in ("left", "top", "width", "height")},
    } for word in words]


def _field(value, evidence: list[dict], state: str = "resolved", raw_evidence: list[dict] | None = None) -> dict:
    # Field confidence is computed only from the word(s) that produced this
    # declaration, never from the average confidence of the whole image.
    confidence = round(sum(float(w.get("conf", 0)) for w in evidence) / len(evidence), 1) if evidence else 0.0
    return {
        "value": value, "state": state, "confidence": confidence,
        "supporting_text": " ".join(w.get("text", "") for w in evidence) or None,
        "provenance": _provenance(evidence),
        "raw_ocr_evidence": _provenance(raw_evidence or []),
    }


def _unresolved(raw_evidence: list[dict] | None = None, ambiguous: bool = False) -> dict:
    return _field(None, [], "ambiguous" if ambiguous else "unresolved", raw_evidence)


def _value_words(words: list[dict], pattern: re.Pattern) -> list[dict]:
    return [word for word in words if pattern.search(word.get("text", "").strip())]


def _label_value(words: list[dict], labels: set[str], values: list[dict], value_pattern: re.Pattern,
                 vertical: int = 220) -> tuple[str | None, list[dict], list[dict]]:
    """Find one deterministic label/value pair, retaining unlabeled candidates."""
    raw = list(values)
    for label in words:
        if _token(label) not in labels:
            continue
        for value_word in values:
            if _nearby(label, value_word, vertical=vertical):
                match = value_pattern.search(value_word.get("text", ""))
                if match:
                    return match.group(0), [label, value_word], raw
    return None, [], raw


def extract_structured_fields(words: list[dict], full_text: str = "") -> dict:
    """Return conservative structured fields, including unresolved evidence."""
    fields: dict[str, dict] = {}

    quantity_words = _value_words(words, QUANTITY)
    if quantity_words:
        match = QUANTITY.search(quantity_words[0]["text"])
        fields["net_quantity"] = _field(match.group(0), [quantity_words[0]])
    else:
        fields["net_quantity"] = _unresolved()

    amount = re.compile(r"(?:₹|rs\.?|inr)?\s*\d{1,5}(?:\.\d{1,2})?\b", re.I)
    # A number embedded in "100 g" is not a price candidate.  Amounts must
    # occupy their own OCR token (possibly with a currency marker).
    amount_words = [word for word in words if amount.fullmatch(word.get("text", "").strip())]
    mrp_labels = {"mrp", "formrp", "maximumretailprice"}
    value, evidence, raw = _label_value(words, mrp_labels, amount_words, amount)
    # A complete MRP declaration in one OCR word is also contextual evidence.
    if not value:
        for word in words:
            match = re.search(r"(?:m\.?r\.?p\.?|maximum\s+retail\s+price)\s*[:.-]?\s*((?:₹|rs\.?|inr)?\s*\d{1,5}(?:\.\d{1,2})?)", word.get("text", ""), re.I)
            if match:
                value, evidence = match.group(1), [word]
                break
    fields["mrp"] = _field(value, evidence) if value else _unresolved(raw, ambiguous=bool(raw or any(_token(w) in mrp_labels or _token(w) in {"rs", "inr", "₹"} for w in words)))

    date_words = _value_words(words, DATE)
    mfg_labels = {"pkd", "packed", "mfd", "mfg", "manufactured", "imported"}
    value, evidence, raw = _label_value(words, mfg_labels, date_words, DATE, vertical=280)
    if not value:
        for word in words:
            match = re.search(r"\b(?:pkd|packed|mfd|mfg|manufactured|imported)\b\s*[:.-]?\s*(%s)" % DATE.pattern, word.get("text", ""), re.I)
            if match:
                value, evidence = match.group(1), [word]
                break
    fields["mfg_date"] = _field(value, evidence) if value else _unresolved(raw, ambiguous=bool(raw and any(_token(w) in mfg_labels for w in words)))

    expiry_labels = {"expiry", "exp", "useby", "bestbefore", "bestbeforedate"}
    value, evidence, raw = _label_value(words, expiry_labels, date_words, DATE, vertical=280)
    if not value:
        for word in words:
            match = re.search(r"\b(?:expiry|exp(?:iry)?|use\s*by|best\s*before)\b\s*[:.-]?\s*(%s)" % DATE.pattern, word.get("text", ""), re.I)
            if match:
                value, evidence = match.group(1), [word]
                break
    fields["expiry"] = _field(value, evidence) if value else _unresolved(raw, ambiguous=bool(raw and any(_token(w) in expiry_labels for w in words)))

    batch_value = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9/-]{1,31}\b")
    batch_labels = {"batch", "batchno", "batchnumber", "lot", "lotno", "lotnumber"}
    candidates = [w for w in words if batch_value.fullmatch(w.get("text", "").strip())
                  and not DATE.search(w.get("text", "").strip())
                  and _token(w) not in batch_labels]
    value, evidence, raw = _label_value(words, batch_labels, candidates, batch_value)
    if not value:
        for word in words:
            match = re.search(r"\b(?:batch|lot)\s*(?:no\.?|number)?\s*[:.-]?\s*([A-Za-z0-9][A-Za-z0-9/-]{1,31})\b", word.get("text", ""), re.I)
            if match:
                value, evidence = match.group(1), [word]
                break
    fields["batch_lot_number"] = _field(value, evidence) if value else _unresolved(raw, ambiguous=any(_token(w) in batch_labels for w in words))

    manufacturer_words = [w for w in words if MANUFACTURER.search(w.get("text", ""))]
    fields["manufacturer"] = _field(manufacturer_words[0]["text"], [manufacturer_words[0]]) if manufacturer_words else _unresolved()

    non_product_labels = mfg_labels | expiry_labels | batch_labels | mrp_labels | {"customercare", "consumercare", "helpline", "tollfree", "inclusive", "tax", "taxes", "netqty", "quantity"}
    product_words = [w for w in words if len(w.get("text", "").strip()) >= 3
                     and any(c.isalpha() for c in w.get("text", ""))
                     and _token(w) not in non_product_labels
                     and not QUANTITY.search(w.get("text", ""))]
    fields["product_name"] = _field(product_words[0]["text"], [product_words[0]]) if product_words else _unresolved()

    contact_words = _value_words(words, CONTACT)
    contact_labels = {"customercare", "consumercare", "helpline", "tollfree"}
    labeled_contact = next(((label, contact) for label in words if _token(label) in contact_labels for contact in contact_words if _nearby(label, contact)), None)
    if labeled_contact:
        label, contact = labeled_contact
        fields["customer_care"] = _field(contact["text"], [label, contact])
    else:
        fields["customer_care"] = _unresolved(contact_words, ambiguous=bool(contact_words))

    # A declaration is a resolved, context-backed field.  Keeping this list
    # makes the recognized printed declarations explicit without inferring
    # missing legal claims from loose OCR text.
    declaration_items = [
        {"field": name, "value": data["value"], "confidence": data["confidence"], "provenance": data["provenance"]}
        for name, data in fields.items() if data["state"] == "resolved"
    ]
    fields["declarations"] = {
        "value": declaration_items or None, "state": "resolved" if declaration_items else "unresolved",
        "confidence": round(sum(item["confidence"] for item in declaration_items) / len(declaration_items), 1) if declaration_items else 0.0,
        "supporting_text": "; ".join(str(item["value"]) for item in declaration_items) or None,
        "provenance": [proof for item in declaration_items for proof in item["provenance"]], "raw_ocr_evidence": [],
    }
    return fields
