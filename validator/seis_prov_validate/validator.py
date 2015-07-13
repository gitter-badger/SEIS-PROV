#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Validator for the SEIS-PROV files.

:copyright:
    Lion Krischer (krischer@geophysik.uni-muenchen.de), 2015
:license:
    BSD 3-Clause ("BSD New" or "BSD Simplified")
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import argparse
import datetime
import inspect
import io
import json
import os
import re
import six
import sys

import jsonschema
from lxml import etree
import prov

# Directory of the file.
_DIR = os.path.dirname(
    os.path.abspath(inspect.getfile(inspect.currentframe())))

_PROV_XML_SCHEMA = os.path.join(_DIR, "schemas", "prov.xsd")
_SEIS_PROV_SCHEMA = os.path.join(_DIR, "schemas", "seis_prov.json")

SEIS_PROV_NAMESPACE = "http://seisprov.org/seis_prov/0.1/#"


def _log_error(message):
    """
    Print the message to stdout and exit with a non-zero exit code.
    """
    sys.exit(message)


def _log_warning(message):
    """
    Print the message to stdout
    """
    print(message)


def validate(filename):
    # Start with the very basic checks. Check if the file exists.
    if not os.path.exists(filename):
        _log_error("Path '%s' does not exist." % filename)
    # Make sure its a file.
    if not os.path.isfile(filename):
        _log_error("Path '%s' is not a file." % filename)

    # Step 1: Check the JSON schema.
    json_schema = _check_json_schema()

    # Step 2: Attempt to read the provenance file with the prov Python package.
    try:
        doc = prov.read(filename)
    except Exception as e:
        _log_error("Could not parse the file with the prov Python library due"
                   " to: the following PROV error message: %s" % (str(e)))

    # Step 3: Validate against the PROV XML XSD Scheme.
    _validate_against_xsd_scheme(doc)

    # Find the seis prov namespace.
    for ns in doc.namespaces:
        if ns.uri == SEIS_PROV_NAMESPACE:
            break
    else:
        _log_error("SEIS-PROV namespace not found in document!")

    # Step 4: Custom validation against the JSON schema. Validate the root
    # document as well as any bundles.
    _validate_prov_bundle(doc, json_schema, ns=ns)
    for bundle in doc.bundles:
        _validate_prov_bundle(bundle, json_schema, ns=ns)


def _validate_prov_bundle(doc, json_schema, ns):
    """
    Custom validator for SEIS-PROV.
    """
    json_schema_map = {
        prov.model.PROV_ENTITY: json_schema["entities"],
        prov.model.PROV_ACTIVITY: json_schema["activities"]}

    for record in doc._records:
        # Now we only care about records in the SEIS-PROV namespace.
        if record.identifier.namespace != ns:
            continue

        # XXX: I honestly don't quite understand this part of the prov API. For
        # now I assume attributes and additional attributes are identical.
        assert record.extra_attributes == record.attributes
        attrs = record.attributes

        rec_type = record.get_type()

        if rec_type not in json_schema_map:
            _log_error("%s not a record type that is valid for SEIS-PROV." %
                       str(rec_type))
        json_def = json_schema_map[rec_type]

        # Find the prov type.
        prov_type = [i for i in attrs if i[0] == prov.model.PROV_TYPE]
        if not prov_type:
            _log_error("Record '%s' does have a prov:type set." %
                       str(record.identifier))
        elif len(prov_type) > 1:
            _log_error("Record '%s' has %i prov:type's set. Only one is "
                       "allowed" % (str(record.identifier), len(prov_type)))
        prov_type = assert_ns_and_extract(prov_type[0][1], ns)

        if prov_type not in json_def:
            _log_error("prov type '%s' of record type '%s' no  valid for "
                       "SEIS-PROV." % (prov_type, str(rec_type)))

        definition = json_def[prov_type]

        # First up, validate the id.
        regex = r"^sp\d{3,5}_%s_[a-z0-9]{7,12}$" % \
            definition["two_letter_code"]
        if re.match(regex, record.identifier.localpart) is None:
            _log_error("Identifier '%s' does not match the regular expression "
                       "'%s'." % (record.identifier.localpart, regex))

        # Validate the label.
        prov_label = [i for i in attrs if i[0] == prov.model.PROV_LABEL]
        if not prov_label:
            _log_error("Record '%s' does have a prov:label set." %
                       str(record.identifier))
        elif len(prov_label) > 1:
            _log_error("Record '%s' has %i prov:label's set. Only one is "
                       "allowed" % (str(record.identifier), len(prov_label)))
        prov_label = prov_label[0][1]
        if definition["label"] != prov_label:
            _log_error("Record '%s' has label '%s' instead of '%s'." % (
                       str(record.identifier), prov_label,
                       definition["label"]))

        # Get all attributes which are part of the seis prov namespace. All
        # others don't matter for the sake of validation.
        attrs = [_i for _i in attrs
                 if isinstance(_i[0], prov.model.QualifiedName) and
                 _i[0].namespace == ns]

        # Make sure it has all required attributes.
        required_attributes = set([_i["name"]
                                   for _i in definition["attributes"]
                                   if _i["required"]])
        available_attributes = set([_i[0].localpart for _i in attrs])
        missing_attributes = required_attributes.difference(
            available_attributes)

        if missing_attributes:
            _log_error("Record '%s' misses the following required "
                       "attributes:\n %s" % (str(record.identifier),
                                             ", ".join(missing_attributes)))

        # Validate each attribute.
        for attr in attrs:
            name, value = attr[0].localpart, attr[1]
            this_def = [i for i in definition["attributes"]
                        if i["name"] == name][0]
            _validate_type(name, value, this_def["types"])

            # Also validate the patterns if any.
            if "pattern" in this_def:
                if "xsd:string" not in this_def["types"]:
                    # This should not happen.
                    raise Exception
                if re.match(this_def["pattern"], value) is None:
                    _log_error("Attribute '%s' in record '%s' with the value "
                               "'%s' does not match the regex '%s'." % (
                                name, str(record.identifier), value,
                                this_def["pattern"]))

TYPE_MAP = {
    "xsd:double": lambda x: isinstance(x, float),
    "xsd:positiveInteger": lambda x: x.value.isnumeric() and int(x.value) >= 0,
    "xsd:string": lambda x: isinstance(x, six.string_types) and bool(x),
    "xsd:dateTime": lambda x: isinstance(x, datetime.datetime)
}


def _validate_type(value_name, value, possible_types):
    """
    Validate the possible types and also check the values if possible.
    """
    for t in possible_types:
        if t not in TYPE_MAP:
            from IPython.core.debugger import Tracer;Tracer(colors="Linux")()
        try:
            if TYPE_MAP[t](value) is True:
                break
        except:
            continue
    else:
        from IPython.core.debugger import Tracer;Tracer(colors="Linux")()
        _log_error("Attribute '%s' has an invalid type '%s'. Valid types: %s"
                   % (value_name, type(value), ", ".join(possible_types)))


def assert_ns_and_extract(name, ns):
    """
    Makes sure the given name is under the given namespace and extract the name.
    """
    prefix = "%s:" % ns.prefix
    if not name.startswith(prefix):
        _log_error("Record %s does not start with %s" % (name, prefix))
    return name.lstrip(prefix)

def _validate_against_xsd_scheme(doc):
    # Serialize to XML (this makes it work with JSON and others as well).
    buf = io.BytesIO()
    doc.serialize(destination=buf, format="xml")
    buf.seek(0, 0)

    xml_doc = etree.parse(buf)
    xml_schema = etree.XMLSchema(etree.parse(_PROV_XML_SCHEMA))

    is_valid = xml_schema.validate(xml_doc)
    if is_valid:
        return

    _log_error("SEIS-PROV document did not pass validation against the "
               "PROV-XML schema:\n\t%s" % "\n\t".join(
                   str(i) for i in xml_schema.error_log))


def _check_json_schema():
    """
    Validate the JSON schema itself to avoid silly errors.
    """
    with io.open(_SEIS_PROV_SCHEMA, "rt") as fh:
        schema = json.load(fh)

    jsonschema.Draft4Validator.check_schema(schema)

    return schema


def main():
    parser = argparse.ArgumentParser(
        description="Validator for SEIS-PROV files.")
    parser.add_argument("filename", help="Filename of the SEIS-PROV file.")
    args = parser.parse_args()

    filename = args.filename

    validate(filename)

    print("Valid SEIS-PROV File!")


if __name__ == "__main__":
    main()
