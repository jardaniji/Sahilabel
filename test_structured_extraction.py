import unittest

from compliance_checker import check_fields
from structured_extraction import extract_structured_fields


def words(*texts, image_id="image_01", filename="front.jpg", variant="original", confidence=90):
    return [{"text": text, "conf": confidence, "left": index * 80, "top": 20,
             "width": 60, "height": 20, "image_id": image_id,
             "source_filename": filename, "variant": variant}
            for index, text in enumerate(texts)]


def report(ocr_words):
    return check_fields({"words": ocr_words, "full_text": "\n".join(word["text"] for word in ocr_words)})


class StructuredExtractionTests(unittest.TestCase):
    def test_contextual_mrp_and_provenance(self):
        data = extract_structured_fields(words("MRP", "Rs. 50.00", "inclusive", "of", "all", "taxes", variant="threshold"))
        self.assertEqual("Rs. 50.00", data["mrp"]["value"])
        self.assertEqual(90.0, data["mrp"]["confidence"])
        self.assertEqual("image_01", data["mrp"]["provenance"][0]["image_id"])
        self.assertEqual("front.jpg", data["mrp"]["provenance"][0]["source_filename"])
        self.assertEqual("threshold", data["mrp"]["provenance"][0]["ocr_variant"])
        self.assertEqual("PASS", next(r["status"] for r in report(words("MRP", "Rs. 50.00", "inclusive", "of", "all", "taxes"))["rules"] if r["rule_id"] == "R18"))

    def test_bare_rs_and_bare_decimal_are_ambiguous_not_mrp(self):
        for text in ("Rs.", "0.50"):
            data = extract_structured_fields(words(text, confidence=99))
            self.assertIsNone(data["mrp"]["value"])
            self.assertEqual("ambiguous", data["mrp"]["state"])
            self.assertEqual("REVIEW", next(r["status"] for r in report(words(text, confidence=99))["rules"] if r["rule_id"] == "R18"))

    def test_quantity_and_mfg_date(self):
        for quantity in ("100 g", "50 ml"):
            data = extract_structured_fields(words(quantity))
            self.assertEqual(quantity, data["net_quantity"]["value"])
            self.assertEqual(90.0, data["net_quantity"]["confidence"])
        data = extract_structured_fields(words("PKD", "06/2026"))
        self.assertEqual("06/2026", data["mfg_date"]["value"])
        self.assertEqual("PKD 06/2026", data["mfg_date"]["supporting_text"])
        self.assertEqual("PASS", next(r["status"] for r in report(words("PKD", "06/2026"))["rules"] if r["rule_id"] == "R15"))

    def test_expiry_and_batch_lot(self):
        data = extract_structured_fields(words("Best Before", "12/2027", "Batch No", "LOT-42A"))
        self.assertEqual("12/2027", data["expiry"]["value"])
        self.assertEqual("LOT-42A", data["batch_lot_number"]["value"])
        self.assertEqual("front.jpg", data["batch_lot_number"]["provenance"][1]["source_filename"])
        self.assertEqual("06/2026", extract_structured_fields(words("MFD: 06/2026"))["mfg_date"]["value"])
        self.assertEqual("ABC-7", extract_structured_fields(words("Batch No: ABC-7"))["batch_lot_number"]["value"])

    def test_one_two_and_four_image_regressions(self):
        # 1 image: contextual quantity remains usable.
        one = report(words("100 g"))
        self.assertEqual("PASS", next(r["status"] for r in one["rules"] if r["rule_id"] == "R10"))
        # 2 images: only the second image contains the MRP declaration.
        two_words = words("Product", image_id="image_01", filename="front.jpg") + words("MRP", "40", "inclusive", "of", "all", "taxes", image_id="image_02", filename="back.jpg")
        two = report(two_words)
        mrp = two["structured_fields"]["mrp"]
        self.assertEqual("40", mrp["value"])
        self.assertEqual("image_02", mrp["provenance"][0]["image_id"])
        self.assertEqual("PASS", next(r["status"] for r in two["rules"] if r["rule_id"] == "R18"))
        # 4 images: a batch declaration on only one side is not mixed with another side.
        four_words = sum((words("front", image_id=f"image_{i:02d}", filename=f"side{i}.jpg") for i in range(1, 4)), []) + words("Lot", "ABC-7", image_id="image_04", filename="side4.jpg")
        four = report(four_words)
        self.assertEqual("ABC-7", four["structured_fields"]["batch_lot_number"]["value"])
        self.assertEqual("image_04", four["structured_fields"]["batch_lot_number"]["provenance"][0]["image_id"])


if __name__ == "__main__":
    unittest.main()
