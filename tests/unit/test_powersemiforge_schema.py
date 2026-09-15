from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from powersemiforge.extractors import PDFParameterExtractor, PDFRule, PlecsXMLExtractor
from powersemiforge.schema import DeviceRecord, ExtractedParameter, Provenance
from powersemiforge.quality import audit_extraction
from powersemiforge.scaffold import scaffold_device
from powersemiforge.modeling import scaffold_model


class PublicSchemaAndExtractionTests(unittest.TestCase):
    def test_pdf_rules_extract_value_and_provenance(self):
        source = Path("example.pdf")
        rules = [PDFRule("VDS_rated", r"Drain.Source Voltage\s*(?P<value>[0-9]+)", "V")]
        values = PDFParameterExtractor.extract_from_pages(source, ["Drain-Source Voltage 1200"], rules, "abc")
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].value, 1200)
        self.assertEqual(values[0].provenance.page, 1)

    def test_plecs_xml_extraction(self):
        fixture = Path(__file__).parents[1] / "fixtures" / "minimal_plecs.xml"
        report = PlecsXMLExtractor().extract(fixture)
        self.assertEqual(report.metadata["part_number"], "EXAMPLE1200")
        self.assertEqual(len(report.tables), 2)
        self.assertEqual([p.value for p in report.parameters], [5.0, 7.5])

    def test_device_record_round_trip_artifact(self):
        parameter = ExtractedParameter("VDS_rated", 1200.0, "V", Provenance("x.pdf", "abc", "test", "1"))
        record = DeviceRecord("1.0", "EXAMPLE1200", "ExampleVendor", "EXAMPLE1200", parameters=[parameter])
        with tempfile.TemporaryDirectory() as temp:
            output = record.save(Path(temp) / "record.json")
            self.assertIn('"device_id": "EXAMPLE1200"', output.read_text(encoding="utf-8"))

    def test_device_model_scaffold_and_quality_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            device = scaffold_device(Path(temp) / "library", "Example Vendor", "EX-1200")
            files = scaffold_model(device, "M0")
            self.assertIn("NotImplementedError", files["model"].read_text(encoding="utf-8"))
            report = PlecsXMLExtractor().extract(Path(__file__).parents[1] / "fixtures" / "minimal_plecs.xml")
            report_path = report.save(Path(temp) / "extraction.json")
            audit = audit_extraction(report_path)
            self.assertEqual(audit["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
