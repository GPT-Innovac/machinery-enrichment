SCORECARD_SCHEMA = {
  "type": "object",
  "additionalProperties": False,
  "properties": {
    "company_type": {
      "type": "string",
      "enum": ["manufacturer", "producer", "dealer", "distributor", "service_provider", "other"]
    },
    "industry_focus": {"type": "array", "items": {"type": "string"}},
    "machine_types": {"type": "array", "items": {"type": "string"}},
    "regions_served": {"type": "array", "items": {"type": "string"}},
    "observations": {"type": "string"},
    "relevance_dach": {"type": "string", "enum": ["high", "medium", "low"]},
    "score_breakdown": {
      "type": "object",
      "additionalProperties": False,
      "properties": {
        "equipment_footprint": {"type": "integer"},
        "dispose_likelihood": {"type": "integer"},
        "alignment": {"type": "integer"},
        "reputation": {"type": "integer"},
        "synergy": {"type": "integer"},
        "dach_access": {"type": "integer"},
        "total": {"type": "integer"}
      },
      "required": ["equipment_footprint", "dispose_likelihood", "alignment", "reputation", "synergy", "dach_access", "total"]
    },
    "recommendation": {"type": "string", "enum": ["yes", "maybe", "no"]},
    "sales_one_liner": {"type": "string"},
    "sales_one_liner_german": {"type": "string"},
    "contact_persons": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
          "name": {"type": ["string", "null"]},
          "title": {"type": "string"},
          "department": {"type": ["string", "null"]},
          "responsibility_match": {"type": "string"},
          "email": {"type": ["string", "null"]},
          "phone": {"type": ["string", "null"]},
          "page_url": {"type": "string"},
          "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
        },
        "required": ["name", "title", "department", "responsibility_match", "email", "phone", "page_url", "confidence"]
      }
    },
    "contact_person_notes": {"type": "string"},
    "sources": {"type": "array", "items": {"type": "string"}}
  },
  "required": [
    "company_type","industry_focus","machine_types","regions_served","observations",
    "relevance_dach","score_breakdown","recommendation","sales_one_liner","sales_one_liner_german",
    "contact_persons","contact_person_notes","sources"
  ]
}
