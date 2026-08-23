from forgecat.db import build_indexes
from forgecat.descriptions import build_invoice_desc
from forgecat.fittings import normalize_fitting_value
from forgecat.pipeline import enrich_row


def test_field_match_invoice_desc():
    attrs = [
        {"attribute_label": "Mounting Type", "attribute_value": "Leg", "attribute_uom": None},
        {"attribute_label": "Voltage Rating", "attribute_value": "120", "attribute_uom": "V"},
    ]
    assert len(build_invoice_desc("Dishwasher", attrs, "FRIGIDAIRE®")) <= 40


def test_fittings_many_to_one():
    build_indexes(force=True)
    assert normalize_fitting_value("Connection Type", "CPLG") == "Coupling"
    assert normalize_fitting_value("Material", "BRS") == "Brass"


def test_dishwasher_hero_row():
    build_indexes(force=True)
    enriched = enrich_row({
        "Mfg_Part_Num": "PDSH4816AF",
        "Part_Desc": "PDSH4816AF Dishwasher SS - Display Only",
        "Part_Manuf": "Appliance Dealers Cooperative (APPDE)",
    })
    assert enriched["BRAND_NAME"] == "FRIGIDAIRE®"
    assert enriched["_depth_tier"] == "A"
