from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

from .base import file_sha256
from ..schema import ExtractedParameter, ExtractionReport, Provenance


class PlecsXMLExtractor:
    name = "plecs_xml"
    version = "1.0"

    @staticmethod
    def _numbers(text: str | None) -> list[float]:
        return [float(value) for value in (text or "").split()]

    def extract(self, source: str | Path) -> ExtractionReport:
        source = Path(source).resolve()
        source_hash = file_sha256(source)
        root = ET.parse(source).getroot()
        namespace = {"p": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
        prefix = "p:" if namespace else ""
        package = root.find(f"{prefix}Package", namespace)
        if package is None:
            raise ValueError("PLECS XML Package element not found")
        parameters = []
        for variable in package.findall(f".//{prefix}Variable", namespace):
            name = variable.findtext(f"{prefix}Name", namespaces=namespace)
            default = variable.findtext(f"{prefix}DefaultValue", namespaces=namespace)
            if name and default is not None:
                parameters.append(ExtractedParameter(
                    name=name, value=float(default), unit="ohm" if name.lower().startswith("rg") else None,
                    provenance=Provenance(str(source), source_hash, self.name, self.version, locator=f"Variable/{name}"),
                    confidence=1.0,
                ))
        tables = []
        for loss_name in ("TurnOnLoss", "TurnOffLoss"):
            loss = package.find(f".//{prefix}{loss_name}", namespace)
            if loss is None:
                continue
            energy = loss.find(f"{prefix}Energy", namespace)
            tables.append({
                "name": loss_name,
                "current_A": self._numbers(loss.findtext(f"{prefix}CurrentAxis", namespaces=namespace)),
                "voltage_V": self._numbers(loss.findtext(f"{prefix}VoltageAxis", namespaces=namespace)),
                "temperature_C": self._numbers(loss.findtext(f"{prefix}TemperatureAxis", namespaces=namespace)),
                "formula": loss.findtext(f"{prefix}Formula", namespaces=namespace),
                "energy_scale": float(energy.attrib.get("scale", "1")) if energy is not None else 1.0,
                "energy_by_temperature": [
                    [self._numbers(voltage.text) for voltage in temperature.findall(f"{prefix}Voltage", namespace)]
                    for temperature in (energy.findall(f"{prefix}Temperature", namespace) if energy is not None else [])
                ],
            })
        return ExtractionReport(
            schema_version="1.0", status="COMPLETE", source_file=str(source), source_sha256=source_hash,
            extractor=f"{self.name}:{self.version}", parameters=parameters, tables=tables,
            metadata={"vendor": package.attrib.get("vendor"), "part_number": package.attrib.get("partnumber"),
                      "device_class": package.attrib.get("class")},
        )

