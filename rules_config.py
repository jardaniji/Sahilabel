"""Authoritative SIH26034 checklist metadata and conservative OCR patterns."""
import re

# Each checklist row remains represented; non-OCR rules are deliberately handled as REVIEW/N/A.
_ROWS = [
('R01','Scope/applicability check','Review'),('R02','Manufacturer name & address','Pass/Fail/Review'),('R03','Packer name & address','Pass/Fail/Review'),('R04','Importer name & address','Pass/Fail/Review'),('R05','Unqualified name/address presumption','Review'),('R06','Brand-owner / marketer liability','Review'),('R07','Complete-address validity','Pass/Fail/Review'),('R08','Common / generic name','Pass/Fail'),('R09','Multi-product name & quantity','Pass/Fail/Review'),('R10','Net quantity declaration','Pass/Fail'),('R11','Net quantity exclusions','Review'),('R12','Quantity accuracy - no variation','Review'),('R13','Quantity accuracy - negligible variation','Review'),('R14',"'When packed' qualifier eligibility",'Pass/Fail/Review'),('R15','Date of manufacture/pre-packing/import','Pass/Fail'),('R16','Date declaration exemptions','Review'),('R17','Packaging-material date carryover','Review'),('R18','MRP declaration format','Pass/Fail'),('R19','MRP exemptions','Review'),('R20','MRP-reduction sticker','Pass/Fail/Review'),('R21','Sticker alteration prohibition (general)','Fail/Review'),('R22','Unit of measurement - below base unit','Pass/Fail'),('R23','Unit of measurement - at/above base unit','Pass/Fail'),('R24','Banned counting terms','Fail/Pass'),('R25','SI units mandatory','Pass/Fail'),('R26','Prohibited vague quantity language','Fail/Pass'),('R27','Additional count declaration (optional)','N/A - informational'),('R28','Consumer care details','Pass/Fail'),('R29','PDP definition / small-package rule','Pass/Fail/Review'),('R30','Unit Sale Price (amendment, unverified)','Pass/Fail/Review'),('R31','Combination/Group/Multi-Piece definitions (amendment, unverified)','Review'),('R32','Dimensions where price-relevant','Pass/Fail'),('R33','Textile/linen dimension declarations','Pass/Fail'),('R34','Usable sheet-count declaration','Pass/Fail'),('R35','Container-commodity declarations','Pass/Fail'),('R36','Letter height - Table I (weight/volume)','Pass/Fail/Review'),('R37','Letter height - Table II (length/area/number)','Pass/Fail/Review'),('R38','Absolute minimum letter height','Pass/Fail'),('R39','PDP clear-zone requirement','Pass/Fail/Review'),('R40','Returnable-bottle MRP placement','Pass/Fail'),('R41','Legibility & contrast','Pass/Fail/Review'),('R42','No reading-through-liquid rule','Review'),('R43','Outer container/wrapper repetition','Pass/Fail/Review'),('R44','Language requirement','Pass/Fail'),('R45','Multi-component package declaration placement','Pass/Fail/Review'),('R46','Wholesale package declarations','Pass/Fail'),('R47','Export package re-labelling','Pass/Fail'),('R48','De-minimis exemption (<=10g/10ml)','Review'),('R49','Fast-food exemption','Review'),('R50','Price-controlled drug formulation exemption','Review'),('R51','Bulk agricultural produce exemption','Review'),('R52','Manufacturer/packer/importer registration','Review'),('R53','Advertisement net-quantity declaration','N/A - out of scope for label scanning'),('R54','Penalty - Rules 27-31 contraventions','N/A - penalty reference only'),('R55','Penalty - residual contraventions','N/A - penalty reference only'),('R56','Maximum Permissible Error - weight/volume','Review'),('R57','Maximum Permissible Error - length/area/number','Review'),('R58','Fourth Schedule unit exceptions','Pass/Fail/Review'),('R59','Sample size for quantity-error testing','N/A - regulatory, not label-level')]
import csv
import io

AUTHORITATIVE_CSV = r"""Rule ID,Check,Applicable When,What to Detect,Result
R01,Scope/applicability check,"All packages, evaluated first",Package type (retail/wholesale/export/institutional/industrial) + net qty vs 25kg/25L threshold (50kg for cement/fertilizer),Review
R02,Manufacturer name & address,"All applicable packages, except food articles",Manufacturer name + complete address text,Pass/Fail/Review
R03,Packer name & address,When manufacturer is not the packer,Packer name + complete address text,Pass/Fail/Review
R04,Importer name & address,Imported packages,Importer name + complete address text,Pass/Fail/Review
R05,Unqualified name/address presumption,Name/address shown without qualifying words,Presence of 'manufactured by' / 'packed by' near the name,Review
R06,Brand-owner / marketer liability,Marketer-labelled packages,'Marketer' label + brand owner address,Review
R07,Complete-address validity,All applicable packages,Address resolves to postal address / city / PIN code,Pass/Fail/Review
R08,Common / generic name,All applicable packages,Product/commodity common name text,Pass/Fail
R09,Multi-product name & quantity,Multi-SKU / combo packages,Name + quantity for each product in the package,Pass/Fail/Review
R10,Net quantity declaration,All applicable packages,Quantity value + unit of weight/measure/number,Pass/Fail
R11,Net quantity exclusions,All applicable packages,Declared quantity excludes wrapper/packaging weight,Review
R12,Quantity accuracy - no variation,Commodities with no environmental variation,Declared quantity equals actual content (needs physical check),Review
R13,Quantity accuracy - negligible variation,Commodities with negligible variation,Declared quantity is not less than actual content,Review
R14,'When packed' qualifier eligibility,"Only Third Schedule commodities (soaps, lotions, creams)",'When packed' phrase present + commodity matches schedule,Pass/Fail/Review
R15,Date of manufacture/pre-packing/import,All applicable packages,"Month + year text (words, numerals, or both)",Pass/Fail
R16,Date declaration exemptions,"Bidi/incense, small PSU LPG, food, seeds, cosmetics",Commodity category match against exemption list,Review
R17,Packaging-material date carryover,Manufacturers using old pre-dated packaging stock,Date validity vs carryover rule; excluded for food with <=90-day shelf life,Review
R18,MRP declaration format,All applicable packages,"Rupee value + 'inclusive of all taxes' wording, correct paise rounding",Pass/Fail
R19,MRP exemptions,"Bidi, price-controlled LPG, alcoholic beverages",Commodity category match against exemption list,Review
R20,MRP-reduction sticker,Sticker present on package,"Lower MRP shown on sticker, original MRP not obscured",Pass/Fail/Review
R21,Sticker alteration prohibition (general),All packages,Sticker covering any declaration other than MRP-reduction,Fail/Review
R22,Unit of measurement - below base unit,Quantity below 1kg/1m/1m2/1m3/1 litre,Correct sub-unit used (g/cm/cm2/cm3/ml),Pass/Fail
R23,Unit of measurement - at/above base unit,Quantity at or above 1kg/1m/1m2/1m3/1 litre,Correct base unit used (kg/m/m2/m3/litre),Pass/Fail
R24,Banned counting terms,All number-based declarations,Presence of 'dozen'/'score'/'gross'/'great gross',Fail/Pass
R25,SI units mandatory,All quantity declarations,Unit is an SI unit; 'N' or 'U' symbol used if sold by number,Pass/Fail
R26,Prohibited vague quantity language,All quantity declarations,Presence of 'minimum'/'about'/'approximately'/'not less than' near quantity,Fail/Pass
R27,Additional count declaration (optional),Mass-declared packages,"Item count present alongside mass (optional, not mandatory)",N/A - informational
R28,Consumer care details,All applicable packages,"Name, address, phone number, email text",Pass/Fail
R29,PDP definition / small-package rule,Packages of 5 cubic centimetres capacity or less,PDP present as a card/tape bearing required info,Pass/Fail/Review
R30,"Unit Sale Price (amendment, unverified)",Where MRP is not equal to unit sale price; excludes Combination/Group/Multi-Piece packages,"Per-unit price value present, rounded to 2 decimal places",Pass/Fail/Review
R31,"Combination/Group/Multi-Piece definitions (amendment, unverified)",Packages containing 2+ individual pieces,Package structure classification (Combination/Group/Multi-Piece),Review
R32,Dimensions where price-relevant,Size-relevant or price-linked commodities,Dimension values present on the package,Pass/Fail
R33,Textile/linen dimension declarations,"Bed-sheets, fabric, dhoties, sarees, towels, similar goods",Number + finished-size dimensions per piece,Pass/Fail
R34,Usable sheet-count declaration,"Foil, tissue, waxed paper, toilet paper, similar sheet products",Sheet count + dimensions of each sheet,Pass/Fail
R35,Container-commodity declarations,"Container-type commodities (bags, boxes, cups, pans)",Number of units + type-specific dimensions (length/width/depth/diameter),Pass/Fail
R36,Letter height - Table I (weight/volume),Weight/volume-declared packages,Numeral height meets Table I band (mm) - values need verification,Pass/Fail/Review
R37,Letter height - Table II (length/area/number),Length/area/number-declared packages,Numeral height meets Table II band (mm) - values need verification,Pass/Fail/Review
R38,Absolute minimum letter height,"All packages, all declarations",Numeral height >= 1mm (2mm if moulded); width >= 1/3 of height,Pass/Fail
R39,PDP clear-zone requirement,All packages,"Clear space around quantity declaration (>=1x height above/below, >=2x left/right)",Pass/Fail/Review
R40,Returnable-bottle MRP placement,Returnable/refillable beverage bottles,MRP shown on crown cap and/or bottle as 'MRP Rs.__/__',Pass/Fail
R41,Legibility & contrast,All packages,Colour contrast of price/quantity numerals against background,Pass/Fail/Review
R42,No reading-through-liquid rule,Liquid-filled transparent packages,Declaration is readable without interference from liquid contents,Review
R43,Outer container/wrapper repetition,Packages with a secondary outer container/wrapper,"All declarations repeated on outer, unless transparent",Pass/Fail/Review
R44,Language requirement,All packages,Hindi (Devanagari) or English text present for every declaration,Pass/Fail
R45,Multi-component package declaration placement,Multi-component commodities sold as one unit,"Declarations on main package with cross-reference, or on each component",Pass/Fail/Review
R46,Wholesale package declarations,Wholesale packages (10+ retail packages or bulk-intermediary),"Manufacturer/importer name & address, commodity identity, count or net quantity",Pass/Fail
R47,Export package re-labelling,Export-labelled packages subsequently sold in India,Chapter II compliant re-labelling present,Pass/Fail
R48,De-minimis exemption (<=10g/10ml),Net quantity 10g/10ml or less,Package quantity vs 10g/10ml and 20g/20ml thresholds,Review
R49,Fast-food exemption,Fast-food items packed by a restaurant/hotel,Commodity/context match against exemption,Review
R50,Price-controlled drug formulation exemption,"Drugs (Price Control) Order, 1995 formulations",Commodity category match against exemption,Review
R51,Bulk agricultural produce exemption,Agricultural farm produce above 50kg,Package quantity vs 50kg threshold,Review
R52,Manufacturer/packer/importer registration,Every pre-packing/importing entity,"Registered entity name/address lookup (business-level, not per-label)",Review
R53,Advertisement net-quantity declaration,MRP-quoting advertisements (not the package label),Net quantity shown in same font size as MRP,N/A - out of scope for label scanning
R54,Penalty - Rules 27-31 contraventions,Violations of Rules 27-31 (registration/advertisement),"Fine amount only (Rs. 4,000) - not detectable from an image",N/A - penalty reference only
R55,Penalty - residual contraventions,Any other Rule violation,"Fine amount only (Rs. 2,000) - not detectable from an image",N/A - penalty reference only
R56,Maximum Permissible Error - weight/volume,Weight/volume commodities not in Fourth Schedule,"Actual vs declared quantity deviation % (needs physical measurement, not OCR) - table values unverified",Review
R57,Maximum Permissible Error - length/area/number,Length/area/number commodities,"Actual vs declared deviation % (needs physical measurement, not OCR) - table values unverified",Review
R58,Fourth Schedule unit exceptions,"~26 named commodities (aerosols, oils, LPG, cosmetics, etc.)",Commodity-specific mandated unit used instead of general default,Pass/Fail/Review
R59,Sample size for quantity-error testing,Regulatory batch testing at manufacturer premises (not per-label),Lot size vs required sample size (32 or 80 units),"N/A - regulatory, not label-level"

"""
RULE_CHECKLIST = [
    {
        'rule_id': row['Rule ID'],
        'check': row['Check'],
        'applicable_when': row['Applicable When'],
        'what_to_detect': row['What to Detect'],
        'expected_result_type': row['Result'],
    }
    for row in csv.DictReader(io.StringIO(AUTHORITATIVE_CSV))
]

QUALIFIED_ENTITY = re.compile(r'\b(mfd\.?\s*by|manufactured\s*by|packed\s*by|imported\s*by|marketed\s*by)\b', re.I)
MANUFACTURER = re.compile(r'\b(mfd\.?\s*by|manufactured\s*by)\b', re.I)
PACKER = re.compile(r'\bpacked\s*by\b', re.I)
IMPORTER = re.compile(r'\bimported\s*by\b', re.I)
MARKETER = re.compile(r'\bmarketed\s*by|marketer\b', re.I)
PIN = re.compile(r'\b\d{6}\b')
QUANTITY = re.compile(r'\b(\d+(?:\.\d+)?)\s*(kg|kgs?|g|gms?|ml|l|lit(?:re|er)s?|m|cm|mm|m\s*[²2]|cm\s*[²2]|m\s*[³3]|cm\s*[³3]|n|u)\b', re.I)
DATE = re.compile(r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*[.\s-]?\d{2,4}|\b\d{1,2}\s*[/-]\s*\d{2,4}\b', re.I)
# Anchors are intentionally required: a bare number must never become MRP evidence.
MRP = re.compile(r'\b(?:m\s*\.?\s*r\s*\.?\s*p\s*\.?|maximum\s+retail\s+price)\s*[:.-]?\s*(?:(?:rs\.?|inr|₹)\s*)?(\d+(?:\.\d{1,2})?)|₹\s*(\d+(?:\.\d{1,2})?)', re.I)
TAX = re.compile(r'inclusive\s*(?:of\s*)?(?:all\s*)?tax(?:es)?', re.I)
CONTACT = re.compile(r'(?:customer|consumer)\s*care|helpline|toll[ -]?free|\b\d{10}\b|[\w.+-]+@[\w.-]+\.\w+', re.I)
BANNED_COUNT = re.compile(r'\b(?:dozen|score|gross|great\s+gross)\b', re.I)
VAGUE_QUANTITY = re.compile(r'\b(?:minimum|about|approximately|not\s+less\s+than)\b', re.I)
DIMENSION = re.compile(r'\b\d+(?:\.\d+)?\s*(?:cm|mm|m|inch|in)\s*(?:x|×)\s*\d+(?:\.\d+)?\s*(?:cm|mm|m|inch|in)\b', re.I)
