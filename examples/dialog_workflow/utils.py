"""
Various local utilities for implementing the dialog workflow.
"""
import csv


# credits: http://stackoverflow.com/questions/5004687/python-csv-dictreader-with-utf-8-data
def UnicodeDictReader(utf8_data, **kwargs):
    """csv.DictReader adapted for Unicode data."""
    csv_reader = csv.DictReader(utf8_data, **kwargs)
    for row in csv_reader:
        yield {key: unicode(value, 'utf-8') for key, value in row.iteritems()}
