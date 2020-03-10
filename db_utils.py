from init_app import mongo
from bson.son import SON


""" custom functions no pipeline """


def regions():
    return sorted(mongo.db.countries_i.distinct("REGION",
                  {"COUNTRY": {"$nin": ["", "null", "Null", None]}}))


""" custom functions yes pipeline """


def db_erp_data():
    pipeline = [
        {
            "$lookup": {
                "from": "weights_i",
                "localField": "WT_ID",
                "foreignField": "ID",
                "as": "Weights"
            }
        },
        {
            "$lookup": {
                "from": "methods_i",
                "localField": "METHOD_ID",
                "foreignField": "ID",
                "as": "Methods"
            }
        },
        {"$unwind": "$Weights"},
        {"$unwind": "$Methods"},
        {
            "$project": {
                "WT": "$Weights.WT",
                "METHOD": "$Methods.METHOD",
                "CATEGORY": "$Methods.CATEGORY",
                "TYPE": "$Methods.TYPE",
                "ERP_PRICE": 1,
                "_id": 0
            }
        }
    ]

    data = list(mongo.db.erp_o.aggregate(pipeline))
    return data


def db_weights_data():
    pipeline = [
        {
            "$lookup": {
                "from": "weights_i",
                "localField": "WT_ID",
                "foreignField": "ID",
                "as": "Weights"
            }
        },
        {
            "$lookup": {
                "from": "yearqm_i",
                "localField": "YEARQM_ID",
                "foreignField": "ID",
                "as": "YearQM"
            }
        },
        {
            "$lookup": {
                "from": "methods_i",
                "localField": "METHOD_ID",
                "foreignField": "ID",
                "as": "Methods"
            }
        },
        {"$unwind": "$Weights"},
        {"$unwind": "$YearQM"},
        {"$unwind": "$Methods"},
        {
            "$project": {
                "DYEAR": "$YearQM.DYEAR",
                "DMONTH": "$YearQM.DMONTH",
                "DDAY": 1,
                "WT": "$Weights.WT",
                "METHOD": "$Methods.METHOD",
                "CATEGORY": "$Methods.CATEGORY",
                "TYPE": "$Methods.TYPE",
                "WT_PRICE": 1,
                "_id": 0
            }
        }
    ]

    data = list(mongo.db.weights_o.aggregate(pipeline))
    return data


def db_tax_data():
    pipeline = [
        {
            "$lookup": {
                "from": "countries_i",
                "localField": "COUNTRY_ID",
                "foreignField": "ID",
                "as": "Country"
            }
        },
        {"$unwind": "$Country"},
        {
            "$project": {
                "COUNTRY": "$Country.COUNTRY",
                "TAX": 1,
                "_id": 0
            }
        },
        {"$sort": SON([("COUNTRY", 1)])}
    ]

    data = list(mongo.db.taxes_o.aggregate(pipeline))
    return data


def db_data(filtering=None):
    pipeline = [
        {
            "$lookup": {
                "from": "countries_i",
                "localField": "COUNTRY_ID",
                "foreignField": "ID",
                "as": "Country"
            }
        },
        {
            "$lookup": {
                "from": "yearqm_i",
                "localField": "YEARQM_ID",
                "foreignField": "ID",
                "as": "YearQM"
            }
        },
        {
            "$lookup": {
                "from": "methods_i",
                "localField": "METHOD_ID",
                "foreignField": "ID",
                "as": "Methods"
            }
        },
        {"$unwind": "$Country"},
        {"$unwind": "$YearQM"},
        {"$unwind": "$Methods"},
        {
            "$project": {
                "DYEAR": "$YearQM.DYEAR",
                "DMONTH": "$YearQM.DMONTH",
                "DDAY": 1,
                "COUNTRY": "$Country.COUNTRY",
                "REGION": "$Country.REGION",
                "METHOD": "$Methods.METHOD",
                "CATEGORY": "$Methods.CATEGORY",
                "TYPE": "$Methods.TYPE",
                "CRP_PRICE": 1,
                "_id": 0
            }
        },
        {"$sort": SON([("COUNTRY", 1), ("METHOD", 1), ("CATEGORY", 1)])}
    ]

    data = list(mongo.db.crp_o.aggregate(pipeline))
    if bool(filtering):
        theRegions = regions()
        filtering = {theRegions[int(f)-1] for f in filtering if f.isdigit()}
        data = [x for x in _filterbyvalue(data, filtering)]
    return data


def _filterbyvalue(seq, values):
    for el in seq:
        for v in values:
            if any([bool(el["COUNTRY"] == v), bool(el["REGION"] == v),
                    bool(el["METHOD"] == v)]):
                yield el
