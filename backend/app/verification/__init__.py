"""Document trust layer, separate from compliance.

Compliance asks "does the evidence meet the requirement?". Verification asks
"can this document's key details be confirmed against the issuer's record?".
A PASS never implies a document is genuine, and VERIFIED never changes a
compliance verdict; only an unconfirmed certificate turns a PASS into REVIEW.
"""
