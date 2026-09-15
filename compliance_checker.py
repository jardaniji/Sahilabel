"""Checklist evaluator. Only image-verifiable evidence receives PASS/FAIL."""
import re
from rules_config import *
from structured_extraction import extract_structured_fields

REVIEW_IDS = {'R01','R06','R11','R12','R13','R16','R17','R19','R21','R36','R37','R38','R39','R41','R42','R52','R56','R57'}
NA_IDS = {'R27','R53','R54','R55','R59'}

def _evidence_sources(words):
    """Summarize OCR evidence by source image without changing rule decisions."""
    sources = {}
    for word in words or []:
        image_id = word.get('image_id', 'image_01')
        source = sources.setdefault(image_id, {'image_id': image_id, 'source_filename': word.get('source_filename'), 'texts': [], 'confidences': []})
        source['texts'].append(word.get('text', ''))
        if word.get('conf') is not None:
            source['confidences'].append(float(word['conf']))
    return [{'image_id': source['image_id'], 'source_filename': source['source_filename'],
             'text': ' '.join(filter(None, source['texts'])),
             'ocr_confidence': round(sum(source['confidences']) / len(source['confidences']), 1) if source['confidences'] else None}
            for source in sources.values()]

def _result(rule, status, detected='', explanation='', words=None):
    localizable_words = words or []
    return {**rule, 'status': status, 'automated_status': status,
            'human_status': None, 'final_status': status,
            'detected_text': detected or None, 'evidence': [detected] if detected else [],
            'evidence_sources': _evidence_sources(localizable_words),
            'explanation': explanation, 'localizable_words': localizable_words}

def _matched_words(words, text):
    if not text: return []
    # Compare normalized OCR tokens so "M.R.P.", "MRP:", "500 g", and
    # "500g" still identify the actual localized words that produced a match.
    tokens = {re.sub(r'[^a-z0-9]', '', token.lower()) for token in re.findall(r'\S+', text)}
    tokens.discard('')
    return [word for word in words if re.sub(r'[^a-z0-9]', '', word.get('text', '').lower()) in tokens]

def _normal_word(word):
    return re.sub(r'[^a-z0-9₹]', '', word.get('text', '').lower())

def _nearby(left, right, horizontal=480, vertical=160):
    """OCR evidence can wrap lines; proximity is safer than concatenating text."""
    return (abs((left['top'] + left['height'] / 2) - (right['top'] + right['height'] / 2)) <= vertical
            and abs((left['left'] + left['width'] / 2) - (right['left'] + right['width'] / 2)) <= horizontal)

def _spatial_mrp(words):
    """Return a label-and-value pair from one image, never a bare Rs. artifact."""
    amounts = []
    for word in words:
        match = re.fullmatch(r'(?:₹|rs|inr)?\s*(\d{1,5}(?:\.\d{1,2})?)', word.get('text', ''), re.I)
        if match:
            amounts.append((word, match.group(1)))
    for label in words:
        token = _normal_word(label)
        # "FORMRP" occurs when an OCR pass joins the printed "FOR MRP";
        # it remains contextual MRP evidence, unlike a free-standing Rs.
        if token not in {'mrp', 'formrp'}:
            continue
        for amount, value in amounts:
            if amount.get('image_id') == label.get('image_id') and _nearby(label, amount):
                return f"{label['text']} {amount['text']}", [label, amount], label.get('image_id')
    # Preserve support for a single correctly read "MRP 45" text sequence.
    for word in words:
        match = MRP.fullmatch(word.get('text', '').strip())
        if match:
            return word['text'], [word], word.get('image_id')
    return '', [], None

def _spatial_date(words):
    labels = {'pkd', 'packed', 'mfd', 'mfg', 'manufactured', 'imported'}
    # OCR commonly keeps DD/MM/YY in one token while the checklist pattern
    # also supports MM/YY.  Search the token so either representation can be
    # linked to its printed PKD/MFD label; the displayed evidence remains the
    # unaltered OCR token.
    date_words = [word for word in words if DATE.search(word.get('text', '').strip())]
    for label in words:
        if _normal_word(label) not in labels:
            continue
        for date in date_words:
            # Price/date panels often put the date on a separate row below
            # PKD/MFD; retain a bounded same-image link rather than treating a
            # date elsewhere on a multi-image inspection as the declaration.
            if date.get('image_id') == label.get('image_id') and _nearby(label, date, horizontal=520, vertical=280):
                return f"{label['text']} {date['text']}", [label, date]
    return '', []

def _has_tax_wording(words, image_id):
    image_text = ' '.join(word.get('text', '') for word in words if word.get('image_id') == image_id)
    if TAX.search(image_text):
        return True
    # OCR can abbreviate printed "INCL.". It is accepted only when a tax
    # token is spatially co-located on the same source image.
    inclusivity = [word for word in words if word.get('image_id') == image_id and _normal_word(word) in {'incl', 'inclusive'}]
    taxes = [word for word in words if word.get('image_id') == image_id and _normal_word(word).startswith('tax')]
    return any(_nearby(left, right, horizontal=280, vertical=100) for left in inclusivity for right in taxes)

def _absence_status(words):
    """Only call absence a violation when OCR produced usable label text."""
    confidence = [float(word['conf']) for word in words if word.get('conf') is not None]
    return 'FAIL' if len(words) >= 8 and confidence and sum(confidence) / len(confidence) >= 50 else 'REVIEW'

def _entity_result(rule, pattern, text, words):
    match = pattern.search(text)
    if not match:
        return _result(rule, 'N/A', explanation='This entity type was not identified on the label; applicability cannot be established from the image.')
    address = PIN.search(text)
    if address:
        found = match.group(0) + '; PIN ' + address.group(0)
        return _result(rule, 'PASS', found, 'A qualified entity label and postal PIN evidence were detected.', _matched_words(words, found))
    return _result(rule, 'REVIEW', match.group(0), 'The entity label was detected, but complete address validity cannot be established from this image.', _matched_words(words, match.group(0)))

def _field_words(field):
    """Turn field provenance back into localizable evidence for the unchanged UI."""
    return [{**entry.get('bbox', {}), 'text': entry.get('text', ''),
             'conf': entry.get('confidence'), 'image_id': entry.get('image_id'),
             'source_filename': entry.get('source_filename'), 'variant': entry.get('ocr_variant')}
            for entry in field.get('provenance', [])]

def _ambiguous(field):
    return field.get('state') == 'ambiguous'

def check_fields(ocr_result: dict) -> dict:
    text, words = ocr_result.get('full_text',''), ocr_result.get('words',[])
    structured = extract_structured_fields(words, text)
    quantity, mrp, mfg_date = structured['net_quantity'], structured['mrp'], structured['mfg_date']
    quantity_match = QUANTITY.search(quantity['value'] or '')
    rules = []
    for rule in RULE_CHECKLIST:
        rid = rule['rule_id']
        if rid in NA_IDS:
            rules.append(_result(rule, 'N/A', explanation='This checklist item is informational, penalty-only, advertisement-only, or regulatory batch testing outside product-label image scanning.')); continue
        if rid in REVIEW_IDS:
            rules.append(_result(rule, 'REVIEW', explanation='This requirement needs physical measurement, package/context classification, calibrated geometry, or an external regulatory/business verification that cannot be reliably completed from a label image.')); continue
        if rid == 'R02':
            m = MANUFACTURER.search(text)
            if m and PIN.search(text): rules.append(_result(rule,'PASS',m.group(0),'Qualified manufacturer label and postal address evidence detected.',_matched_words(words,m.group(0))))
            elif m: rules.append(_result(rule,'REVIEW',m.group(0),'Manufacturer label detected, but a complete address cannot be reliably verified.',_matched_words(words,m.group(0))))
            else: rules.append(_result(rule,'REVIEW',explanation='Manufacturer applicability may be affected by product category; no qualified manufacturer declaration was detected.'))
        elif rid == 'R03': rules.append(_entity_result(rule, PACKER, text, words))
        elif rid == 'R04': rules.append(_entity_result(rule, IMPORTER, text, words))
        elif rid == 'R05':
            if QUALIFIED_ENTITY.search(text): rules.append(_result(rule,'N/A',explanation='Qualified manufacturer/packer/importer wording was detected.'))
            else: rules.append(_result(rule,'REVIEW',explanation='Whether an unqualified name/address appears and should be presumed attributable needs human review.'))
        elif rid == 'R07':
            found = PIN.search(text).group(0) if PIN.search(text) else ''
            rules.append(_result(rule,'PASS' if found else 'REVIEW', found, 'Postal PIN evidence was detected.' if found else 'Address validity cannot be confirmed from OCR alone.', _matched_words(words, found)))
        elif rid == 'R08':
            candidate = next((line.strip() for line in text.splitlines() if len(line.strip()) >= 3 and any(c.isalpha() for c in line)), None)
            rules.append(_result(rule,'PASS' if candidate else 'FAIL',candidate or '', 'A product-name candidate was found.' if candidate else 'No alphabetic commodity-name candidate was detected.'))
        elif rid == 'R09': rules.append(_result(rule,'N/A',explanation='No reliable multi-SKU/combo package classification was detected.'))
        elif rid == 'R10':
            found = quantity['value'] or ''
            status = 'PASS' if found else ('REVIEW' if _ambiguous(quantity) else _absence_status(words))
            rules.append(_result(rule, status, found, 'Quantity value and unit detected.' if found else ('Quantity OCR evidence is ambiguous; human review is needed.' if status == 'REVIEW' else 'No quantity value with a supported unit was detected.'), _field_words(quantity)))
        elif rid == 'R14':
            m = re.search(r'when\s+packed',text,re.I)
            rules.append(_result(rule,'REVIEW' if m else 'N/A',m.group(0) if m else '', 'Third Schedule commodity eligibility requires product classification.' if m else 'No “when packed” qualifier detected.'))
        elif rid == 'R15':
            if mfg_date['value']:
                rules.append(_result(rule,'PASS',mfg_date['supporting_text'],'A date is spatially linked to a manufacture/pre-pack/import label.',_field_words(mfg_date)))
            else:
                status = 'REVIEW' if _ambiguous(mfg_date) else _absence_status(words)
                rules.append(_result(rule,status,explanation='No date was linked to a manufacture/pre-pack/import label.' if status == 'FAIL' else 'A date declaration could not be reliably linked to its label; human review is needed.'))
        elif rid == 'R18':
            if not mrp['value']:
                status = 'REVIEW' if _ambiguous(mrp) else _absence_status(words)
                rules.append(_result(rule,status,explanation='No contextual MRP label and price value were detected.' if status == 'FAIL' else 'MRP evidence is insufficient or ambiguous; human review is needed.'))
            elif _has_tax_wording(words, _field_words(mrp)[0].get('image_id')):
                rules.append(_result(rule,'PASS',mrp['supporting_text'],'MRP label, value, and inclusive-tax wording were detected on the same image.',_field_words(mrp)))
            else:
                rules.append(_result(rule,'FAIL',mrp['supporting_text'],'MRP label and value were detected, but required inclusive-tax wording was not detected on that image.',_field_words(mrp)))
        elif rid == 'R20':
            m = re.search(r'\bsticker\b', text, re.I)
            rules.append(_result(rule, 'REVIEW' if m else 'N/A', m.group(0) if m else '', 'A sticker reference needs visual review for MRP reduction compliance.' if m else 'No sticker evidence was detected; this conditional rule is not applicable from the label evidence.', _matched_words(words, m.group(0) if m else '')))
        elif rid == 'R29':
            m = re.search(r'\b(?:\d+(?:\.\d+)?\s*(?:ml|cm\s*[³3])|small\s+package)\b', text, re.I)
            rules.append(_result(rule, 'REVIEW' if m else 'N/A', m.group(0) if m else '', 'Small-package PDP applicability needs physical/package-context review.' if m else 'No small-package evidence was detected.'))
        elif rid == 'R30':
            m = re.search(r'\b(?:unit\s+(?:sale\s+)?price|price\s+per)\b', text, re.I)
            rules.append(_result(rule, 'REVIEW' if m else 'N/A', m.group(0) if m else '', 'Unit sale price wording was detected and needs applicability review.' if m else 'No unit-sale-price evidence was detected.'))
        elif rid == 'R31':
            m = re.search(r'\b(?:combo|multipack|multi[- ]?piece|pack\s+of|\d+\s+pieces?)\b', text, re.I)
            rules.append(_result(rule, 'REVIEW' if m else 'N/A', m.group(0) if m else '', 'Potential multi-piece packaging needs human classification.' if m else 'No multi-piece package evidence was detected.'))
        elif rid in {'R22','R23','R25'}:
            if not quantity_match: rules.append(_result(rule,'REVIEW' if _ambiguous(quantity) else 'N/A',explanation='Quantity OCR evidence is ambiguous; human review is needed.' if _ambiguous(quantity) else 'No quantity declaration was available to evaluate unit formatting.'))
            else:
                value, unit = float(quantity_match.group(1)), quantity_match.group(2).lower()
                if rid == 'R22': ok = (unit in {'g','gm','gms','ml','cm','mm'} or value >= 1)
                elif rid == 'R23': ok = not (value >= 1000 and unit in {'g','gm','gms','ml'})
                else: ok = unit in {'kg','g','gm','gms','ml','l','litre','litres','m','cm','mm','m2','cm2','m3','cm3','n','u'}
                found = quantity_match.group(0)
                rules.append(_result(rule,'PASS' if ok else 'FAIL',found,'Quantity unit format satisfies the image-verifiable rule.' if ok else 'Detected quantity unit format does not satisfy the image-verifiable rule.', _field_words(quantity)))
        elif rid == 'R24':
            found = BANNED_COUNT.search(text).group(0) if BANNED_COUNT.search(text) else ''
            rules.append(_result(rule,'FAIL' if found else 'PASS',found, 'A banned counting term was detected.' if found else 'No banned counting term was detected.', _matched_words(words, found)))
        elif rid == 'R26':
            found = VAGUE_QUANTITY.search(text).group(0) if VAGUE_QUANTITY.search(text) else ''
            rules.append(_result(rule,'FAIL' if found else 'PASS',found, 'Vague quantity language was detected.' if found else 'No prohibited vague quantity language was detected.', _matched_words(words, found)))
        elif rid == 'R28':
            customer_care = structured['customer_care']
            found = customer_care['value'] or ''
            status = 'PASS' if found else ('REVIEW' if _ambiguous(customer_care) else _absence_status(words))
            rules.append(_result(rule, status, found, 'Consumer contact evidence detected.' if found else ('Consumer-contact OCR evidence is ambiguous; human review is needed.' if status == 'REVIEW' else 'No consumer care contact evidence detected.'), _field_words(customer_care)))
        elif rid in {'R32','R33','R34','R35'}: rules.append(_result(rule,'N/A',explanation='The product category required for this conditional dimension rule was not reliably identified.'))
        elif rid == 'R40': rules.append(_result(rule,'N/A',explanation='No returnable/refillable beverage bottle classification was detected.'))
        elif rid == 'R43':
            m = re.search(r'\b(?:outer\s+(?:pack|wrapper|container)|wrapper)\b', text, re.I)
            rules.append(_result(rule, 'REVIEW' if m else 'N/A', m.group(0) if m else '', 'Outer-package wording needs visual repetition review.' if m else 'No outer-container evidence was detected.'))
        elif rid == 'R44':
            has_language = any(c.isascii() and c.isalpha() for c in text) or any('\u0900' <= c <= '\u097f' for c in text)
            rules.append(_result(rule,'PASS' if has_language else 'FAIL',explanation='English or Devanagari text was detected in OCR output.' if has_language else 'No English or Devanagari text was detected.'))
        elif rid == 'R45':
            m = re.search(r'\b(?:component|assembly|kit|combo)\b', text, re.I)
            rules.append(_result(rule, 'REVIEW' if m else 'N/A', m.group(0) if m else '', 'Multi-component wording needs placement review.' if m else 'No multi-component evidence was detected.'))
        elif rid == 'R46': rules.append(_result(rule,'N/A',explanation='No wholesale-package classification was detected.'))
        elif rid == 'R47': rules.append(_result(rule,'N/A',explanation='No export-labelled package classification was detected.'))
        elif rid == 'R48':
            small = quantity_match.group(0) if quantity_match and float(quantity_match.group(1)) <= 10 and quantity_match.group(2).lower() in {'g','gm','gms','ml'} else ''
            rules.append(_result(rule, 'REVIEW' if small else 'N/A', small, 'A de-minimis quantity was detected and needs exemption review.' if small else 'No <=10g/10ml quantity evidence was detected.', _field_words(quantity)))
        elif rid == 'R49':
            m = re.search(r'\b(?:restaurant|hotel|fast\s*food)\b', text, re.I)
            rules.append(_result(rule, 'REVIEW' if m else 'N/A', m.group(0) if m else '', 'Fast-food context needs human exemption review.' if m else 'No fast-food context evidence was detected.'))
        elif rid == 'R50':
            m = re.search(r'\b(?:drug|tablet|capsule|formulation)\b', text, re.I)
            rules.append(_result(rule, 'REVIEW' if m else 'N/A', m.group(0) if m else '', 'Drug context needs exemption review.' if m else 'No drug-formulation evidence was detected.'))
        elif rid == 'R51':
            m = re.search(r'\b(?:agricultural|farm\s+produce|fertilizer)\b', text, re.I)
            rules.append(_result(rule, 'REVIEW' if m else 'N/A', m.group(0) if m else '', 'Agricultural context needs exemption review.' if m else 'No bulk agricultural produce evidence was detected.'))
        elif rid == 'R58':
            m = re.search(r'\b(?:aerosol|lpg|cosmetic|edible\s+oil)\b', text, re.I)
            rules.append(_result(rule, 'REVIEW' if m else 'N/A', m.group(0) if m else '', 'Potential Fourth Schedule commodity needs classification review.' if m else 'No Fourth Schedule commodity evidence was detected.'))
        else: rules.append(_result(rule,'REVIEW',explanation='Human review is required for this checklist item.'))
    descriptions = {'manufacturer':'Manufacturer declaration', 'product_name':'Common/generic name of commodity', 'net_quantity':'Net quantity', 'mrp':'MRP inclusive of taxes', 'mfg_date':'Month & year declaration', 'expiry':'Expiry / use-by / best-before', 'batch_lot_number':'Batch / lot number', 'customer_care':'Consumer care details', 'declarations':'Context-backed declarations'}
    severity = {'customer_care':'moderate', 'declarations':'informational'}
    legacy_rule = {'manufacturer':'R02', 'product_name':'R08', 'net_quantity':'R10', 'mrp':'R18', 'mfg_date':'R15', 'customer_care':'R28'}
    legacy = {}
    for name, field in structured.items():
        key = 'manufacturer_info' if name == 'manufacturer' else name
        rule_id = legacy_rule.get(name)
        present = next(r['status'] for r in rules if r['rule_id'] == rule_id) == 'PASS' if rule_id else field['state'] == 'resolved'
        legacy[key] = {**field, 'present': present, 'matched_text': field['supporting_text'], 'description': descriptions[name], 'severity': severity.get(name, 'critical')}
    failed=any(r['status']=='FAIL' for r in rules); review=any(r['status']=='REVIEW' for r in rules)
    return {'overall_compliant': not failed and not review,'overall_status':'FAIL' if failed else ('REVIEW' if review else 'PASS'),'fields':legacy,'structured_fields':structured,'readability_flags':[],'notes':[],'rules':rules}
