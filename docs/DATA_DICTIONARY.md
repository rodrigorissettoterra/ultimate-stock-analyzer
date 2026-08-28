# Data Dictionary v0.1

Canonical financial observations must support these fields:

| Field | Meaning |
|---|---|
| ticker | trading symbol for the security |
| company_id | stable internal issuer identifier |
| metric | canonical metric name |
| value | numeric observation; null when unknown |
| unit | BRL, %, shares, ratio, etc. |
| reference_date | economic/accounting period represented |
| publication_date | date the source document was published |
| available_from | earliest timestamp the model may use in point-in-time analysis |
| collected_at | timestamp collected by our system |
| source | provider/source authority |
| source_document | source document/file identifier |
| revision | monotonically increasing restatement/revision number |

Never replace unknown values with invented estimates. Derived values must retain lineage to their input observations and formula/model version.
