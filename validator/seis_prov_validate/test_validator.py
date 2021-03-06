#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test cases for the SEIS-PROV validator.

Execute with (requires pytest to be installed):

$ py.test test_validator.py

or

$ python -m seis_prov_validate.test_validator


:copyright:
    Lion Krischer (lion.krischer@googlemail.com), 2015
:license:
    BSD 3-Clause ("BSD New" or "BSD Simplified")
"""
import glob
import inspect
import io
import os
import pytest
import sys

from seis_prov_validate.validator import validate

# Most generic way to get the data folder path.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(
    inspect.getfile(inspect.currentframe()))), "test_data")

# Find all valid files.
VALID_FILES = {
    os.path.basename(_i): os.path.abspath(_i) for _i in
    glob.glob(os.path.join(DATA_DIR, "valid_files", "*.xml")) +
    glob.glob(os.path.join(DATA_DIR, "valid_files", "*.json"))}

# Make sure the globbing expression is not completely wrong.
assert len(VALID_FILES)

# Find all invalid files.
INVALID_FILES = {
    os.path.basename(_i): os.path.abspath(_i) for _i in
    glob.glob(os.path.join(DATA_DIR, "invalid_files", "*.xml")) +
    glob.glob(os.path.join(DATA_DIR, "invalid_files", "*.json"))}

# Make sure the globbing expression is not completely wrong.
assert len(INVALID_FILES)


@pytest.mark.parametrize("filename", sorted(VALID_FILES.values()))
def test_valid_files(filename):
    """
    Make sure all files that should be valid are valid.
    """
    assert validate(filename).is_valid is True


@pytest.mark.parametrize("filename", sorted(VALID_FILES.values()))
def test_valid_files_from_bytesio(filename):
    """
    Make sure all files that should be valid are valid if they are read from a
    BytesIO object.
    """
    with open(filename, "rb") as fh:
        with io.BytesIO(fh.read()) as buf:
            assert validate(buf).is_valid is True


@pytest.mark.parametrize("filename", sorted(VALID_FILES.values()))
def test_valid_files_from_an_open_file(filename):
    """
    Make sure all files that should be valid are valid if they are read from
    open file objects.
    """
    with open(filename, "rb") as fh:
        assert validate(fh).is_valid is True


@pytest.mark.parametrize("filename", sorted(INVALID_FILES.values()))
def test_invalid_files(filename):
    """
    Make sure all files that should be invalid are invalid.
    """
    assert validate(filename).is_valid is False


@pytest.mark.parametrize("filename", sorted(INVALID_FILES.values()))
def test_invalid_files_from_bytesio(filename):
    """
    Make sure all files that should be invalid are invalid if they are read
    from a BytesIO object.
    """
    with open(filename, "rb") as fh:
        with io.BytesIO(fh.read()) as buf:
            assert validate(buf).is_valid is False


@pytest.mark.parametrize("filename", sorted(INVALID_FILES.values()))
def test_invalid_files_from_an_open_file(filename):
    """
    Make sure all files that should be invalid are invalid if they are read
    from open file objects.
    """
    with open(filename, "rb") as fh:
        assert validate(fh).is_valid is False


def test_software_agent_missing_website():
    result = validate(INVALID_FILES["software_agent_missing_website.xml"])
    assert result.is_valid is False
    assert result.errors == [
        "Record 'seis_prov:sp001_sa_9345084' misses the following required "
        "attributes in the SEIS-PROV namespace: 'website'"]

    assert result.warnings == []


def test_software_agent_missing_multiple_attributes():
    result = validate(
        INVALID_FILES["software_agent_missing_multiple_attributes.xml"])
    assert result.is_valid is False
    assert result.errors == [
        "Record 'seis_prov:sp001_sa_9345084' misses the following required "
        "attributes in the SEIS-PROV namespace: 'software_name', "
        "'software_version', 'website'"]

    assert result.warnings == []


def test_non_existent_path():
    result = validate("some/random/path/that/does/not/exist")
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Path 'some/random/path/that/does/not/exist' does not exist."]


def test_validating_folder():
    result = validate(DATA_DIR)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Path '%s' is not a file." % DATA_DIR]


def test_validating_random_other_file():
    filename = os.path.join(DATA_DIR, "invalid_files", "random_text_file.txt")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "File is neither a valid JSON nor a valid XML file."]


def test_validating_random_json_file():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "random_json_file.json")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert len(result.errors) == 1
    assert result.errors[0].startswith(
        "Could not parse the file with the prov Python library due to: the "
        "following PROV error message:")


def test_validating_random_xml_file():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "random_xml_file.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert len(result.errors) == 1
    assert result.errors[0].startswith(
        "SEIS-PROV namespace not found in document!")


def test_empty_seis_prov_documents():
    """
    These are valid but at least a warning should be shown to alert the users.
    """
    filename = os.path.join(DATA_DIR, "valid_files",
                            "empty_seis_prov_document.xml")
    result = validate(filename)
    assert result.is_valid is True
    assert result.errors == []
    assert result.warnings == ["The document is a valid W3C PROV document but "
                               "not a single SEIS-PROV record has been found."]

    filename = os.path.join(DATA_DIR, "valid_files",
                            "empty_seis_prov_document.json")
    result = validate(filename)
    assert result.is_valid is True
    assert result.errors == []
    assert result.warnings == ["The document is a valid W3C PROV document but "
                               "not a single SEIS-PROV record has been found."]


def test_seis_prov_document_with_two_types():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "entity_with_two_prov_types.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Record 'seis_prov:sp001_wf_c17dd1f' has 2 prov:type's set. Only one "
        "is allowed as soon as any prov:type or the record's id is in the "
        "SEIS-PROV namespace."]


def test_prov_document_with_no_types():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "entity_with_no_prov_type.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Record 'seis_prov:sp001_wf_c17dd1f' has an id in the SEIS-PROV "
        "namespace but no prov:type attribute. This is not allowed."]


def test_prov_document_with_two_types():
    """
    A pure PROV record can have two types. No problem.
    """
    filename = os.path.join(
        DATA_DIR, "valid_files",
        "record_with_two_types_but_not_in_seis_prov_ns.xml")
    result = validate(filename)
    assert result.is_valid is True
    assert result.errors == []
    assert result.warnings == ["The document is a valid W3C PROV document but "
                               "not a single SEIS-PROV record has been found."]


def test_seis_prov_record_with_two_types_and_one_in_seis_prov_namespace():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "record_with_two_types_in_seis_prov_ns.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Record 'tr:WD-prov-dm-20111215' has 2 prov:type's set. Only one is "
        "allowed as soon as any prov:type or the record's id is in the "
        "SEIS-PROV namespace."]


def test_seis_prov_record_with_two_types_and_seis_prov_id():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "record_with_two_types_but_id_in_seis_prov.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Record 'seis_prov:WD-prov-dm-20111215' has 2 prov:type's set. Only "
        "one is allowed as soon as any prov:type or the record's id is in the "
        "SEIS-PROV namespace."]


def test_normal_prov_record_but_seis_prov_type():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "record_non_sp_ns_but_sp_type.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Record 'tr:sp001_wf_c17dd1f' has a prov:type attribute in the "
        "SEIS-PROV namespace but its id is not part of the namespace. This "
        "is not allowed."]


def test_seis_prov_record_but_wrong_type():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "record_seis_prov_id_but_wrong_type.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Record 'seis_prov:sp001_wf_c17dd1f' has an id in the SEIS-PROV "
        "namespace but its prov:type is neither in the SEIS-PROV "
        "namespace nor is it a person, an organization, or a software agent."
        " This is not allowed."]


def test_unknown_seis_prov_type():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "unknown_seis_prov_type.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "prov:type 'something_unknown' of record type 'prov:Entity' is not "
        "known to SEIS-PROV."]


def test_no_prov_label():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "no_label.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Record 'seis_prov:sp001_wf_c17dd1f' does not have a prov:label set."]


def test_many_prov_label():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "many_label.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == ["Record 'seis_prov:sp001_wf_c17dd1f' has 3 "
                             "prov:label's set. Only one is allowed."]


def test_wrong_prov_label():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "wrong_label.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Record 'seis_prov:sp001_wf_c17dd1f' has label 'Random Label' instead "
        "of 'Waveform Trace'."]


def test_additional_attribute():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "waveform_with_extra_attribute.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Record 'seis_prov:sp001_wf_c17dd1f' has an additional attribute in "
        "the SEIS-PROV namespace: 'something'. This is not allowed for this "
        "record type."]


def test_wrong_pattern_in_attribute():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "wrong_pattern_in_attribute.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Attribute 'seed_id' in record 'seis_prov:sp001_wf_8afb672' with the "
        "value '12BW.FURT..EHZ' does not match the regex "
        "'^[A-Z0-9]{1,2}\\.[A-Z0-9]{1,5}\\.[A-Z0-9]{0,2}\\.[A-Z0-9]{3}$'."]


def test_wrong_type_in_attr_string_instead_of_float():
    filename = os.path.join(DATA_DIR, "invalid_files",
                            "wrong_type_in_attribute_str_instead_of_float.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert len(result.errors) == 1
    assert "could not convert string to float" in result.errors[0].lower()


def test_wrong_type_in_attr_string_negative_instead_of_positive_integer():
    filename = os.path.join(
        DATA_DIR, "invalid_files",
        "wrong_type_in_attribute_negative_instead_of_positive_integer.xml")
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert len(result.errors) == 1
    assert "not a valid value of the atomic type" in result.errors[0].lower()


def test_detrending_with_wrong_method():
    filename = INVALID_FILES["detrend_wrong_method.xml"]
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "Attribute 'detrending_method' in record 'seis_prov:sp001_dt_4e3a746' "
        "with the value 'random' does not match the regex "
        "'linear fit|demean|simple'."]


def test_non_valid_id():
    filename = INVALID_FILES["person_with_invalid_id.xml"]
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "The local part of the identifier 'seis_prov:pp_me' does not match "
        "the regular expression '^sp\\d{3,5}_pp_[a-z0-9]{7,12}$' as is "
        "required by the standard."]


def test_duplicate_id():
    filename = INVALID_FILES["duplicate_ids.xml"]
    result = validate(filename)
    assert result.is_valid is False
    assert result.warnings == []
    assert result.errors == [
        "One or more ids have been used more than once: 'sp001_wf_c17dd1f'"
    ]


if __name__ == "__main__":
    PATH = os.path.dirname(os.path.abspath(inspect.getfile(
                           inspect.currentframe())))
    sys.exit(pytest.main(PATH))
