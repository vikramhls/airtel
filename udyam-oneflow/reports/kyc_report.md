# Smart KYC batch report (12 synthetic applicants)

Reference date 2026-07-15. OCR engine: rapidocr. Registries are the mock CSVs. Identifiers are masked.

| Applicant | Business | Score | State | Exceptions |
|---|---|---|---|---|
| K01 | Vindhya Tours & Travels | 16/18 | red | GSTIN_ACTIVE, UDYAM_FORMAT |
| K02 | Harmony Dentai Care | 21/21 | green | none |
| K03 | Ganesh Woodcraft | 21/21 | green | none |
| K04 | Saffron Dental Care LLP | 14/15 | red | DOC_QUALITY |
| K05 | Balaji Realty LLP | 16/17 | red | DOC_PRESENT_UDYAM |
| K06 | Saffron Unisex Salon | 16/18 | red | GSTIN_CHECKSUM, GSTIN_REGISTRY |
| K07 | Neelgiri Physio Clinic | 21/21 | green | none |
| K08 | Green Leaf Legal Associates | 21/21 | green | none |
| K09 | Kaveri Insurance Advisors | 21/21 | green | none |
| K10 | Kaveri Stays LLP | 21/21 | green | none |
| K11 | Trinity Bake House Pvt Ltd | 20/21 | red | ADDR_DATE_FRESH |
| K12 | Star Electronics | 21/21 | green | none |

## K01

**Summary:** Gstin Active: Your GSTIN shows as Cancelled. You can still buy products that do not need a GSTIN. Udyam Format: The Udyam number on the certificate is missing or invalid.

**Next action:** Udyam number is missing or invalid - re-enter it from the certificate (UDYAM-XX-00-0000000).

| Check | Result | Detail |
|---|---|---|
| CONSENT_RECORDED | PASS | Consent recorded for KYC verification. |
| DOC_PRESENT_GST | PASS | Gst certificate received. |
| DOC_PRESENT_UDYAM | PASS | Udyam certificate received. |
| DOC_PRESENT_ADDR | PASS | Address proof received. |
| DOC_PRESENT_ID | PASS | Signatory id received. |
| DOC_QUALITY | PASS | All document images are sharp enough to read. |
| GSTIN_FORMAT | PASS | GSTIN 37••••••••••1ZS has the right 15-character structure. |
| GSTIN_CHECKSUM | PASS | GSTIN checksum verified. |
| GSTIN_REGISTRY | PASS | Found 37••••••••••1ZS in the mock GST registry. |
| GSTIN_ACTIVE | FAIL (warning) | Your GSTIN shows as Cancelled. You can still buy products that do not need a GSTIN. |
| GST_NAME_MATCH | PASS | Name on the certificate matches the registry (100% similar). |
| GST_ADDR_MATCH | PASS | Address matches the registry (100%). |
| UDYAM_FORMAT | FAIL (blocker) | The Udyam number on the certificate is missing or invalid. |
| ADDR_DATE_FRESH | PASS | Bill is 19 days old (limit 90). |
| ADDR_MATCHES_BUSINESS | PASS | Bill address and name match your business (100%, 100%). |
| ID_FORMAT | PASS | ID number SYN-ID-•••6190 has the expected format. |
| ID_NOT_EXPIRED | PASS | ID valid till 2028-03-26. |
| ID_NAME_BUSINESS | PASS | Signatory is the proprietor of this business (100% business, 100% name). |

## K02

**Summary:** All checks passed. This application is ready.

| Check | Result | Detail |
|---|---|---|
| CONSENT_RECORDED | PASS | Consent recorded for KYC verification. |
| DOC_PRESENT_GST | PASS | Gst certificate received. |
| DOC_PRESENT_UDYAM | PASS | Udyam certificate received. |
| DOC_PRESENT_ADDR | PASS | Address proof received. |
| DOC_PRESENT_ID | PASS | Signatory id received. |
| DOC_QUALITY | PASS | All document images are sharp enough to read. |
| GSTIN_FORMAT | PASS | GSTIN 19••••••••••1ZL has the right 15-character structure. |
| GSTIN_CHECKSUM | PASS | GSTIN checksum verified. |
| GSTIN_REGISTRY | PASS | Found 19••••••••••1ZL in the mock GST registry. |
| GSTIN_ACTIVE | PASS | GSTIN status is Active. |
| GST_NAME_MATCH | PASS | Name on the certificate matches the registry (100% similar). |
| GST_ADDR_MATCH | PASS | Address matches the registry (95%). |
| UDYAM_FORMAT | PASS | Udyam number UDYAM-WB-00-•••3330 looks valid. |
| UDYAM_REGISTRY | PASS | Found in the mock Udyam registry. |
| UDYAM_NAME_MATCH | PASS | Enterprise name matches your other documents (100%). |
| UDYAM_LOCATION | PASS | Udyam city and state match the registry and your GSTIN. |
| ADDR_DATE_FRESH | PASS | Bill is 54 days old (limit 90). |
| ADDR_MATCHES_BUSINESS | PASS | Bill address and name match your business (95%, 100%). |
| ID_FORMAT | PASS | ID number SYN-ID-•••6907 has the expected format. |
| ID_NOT_EXPIRED | PASS | ID valid till 2028-09-10. |
| ID_NAME_BUSINESS | PASS | Signatory is the proprietor of this business (100% business, 100% name). |

## K03

**Summary:** All checks passed. This application is ready.

| Check | Result | Detail |
|---|---|---|
| CONSENT_RECORDED | PASS | Consent recorded for KYC verification. |
| DOC_PRESENT_GST | PASS | Gst certificate received. |
| DOC_PRESENT_UDYAM | PASS | Udyam certificate received. |
| DOC_PRESENT_ADDR | PASS | Address proof received. |
| DOC_PRESENT_ID | PASS | Signatory id received. |
| DOC_QUALITY | PASS | All document images are sharp enough to read. |
| GSTIN_FORMAT | PASS | GSTIN 27••••••••••1ZP has the right 15-character structure. |
| GSTIN_CHECKSUM | PASS | GSTIN checksum verified. |
| GSTIN_REGISTRY | PASS | Found 27••••••••••1ZP in the mock GST registry. |
| GSTIN_ACTIVE | PASS | GSTIN status is Active. |
| GST_NAME_MATCH | PASS | Name on the certificate matches the registry (100% similar). |
| GST_ADDR_MATCH | PASS | Address matches the registry (98%). |
| UDYAM_FORMAT | PASS | Udyam number UDYAM-MH-00-•••6696 looks valid. |
| UDYAM_REGISTRY | PASS | Found in the mock Udyam registry. |
| UDYAM_NAME_MATCH | PASS | Enterprise name matches your other documents (100%). |
| UDYAM_LOCATION | PASS | Udyam city and state match the registry and your GSTIN. |
| ADDR_DATE_FRESH | PASS | Bill is 46 days old (limit 90). |
| ADDR_MATCHES_BUSINESS | PASS | Bill address and name match your business (100%, 100%). |
| ID_FORMAT | PASS | ID number SYN-ID-•••7889 has the expected format. |
| ID_NOT_EXPIRED | PASS | ID valid till 2028-07-04. |
| ID_NAME_BUSINESS | PASS | Signatory is the proprietor of this business (100% business, 100% name). |

## K04

**Summary:** Doc Quality: Too blurry to read: GST certificate.

**Next action:** Retake the photo of your GST certificate in good light, or type the details in yourself.

| Check | Result | Detail |
|---|---|---|
| CONSENT_RECORDED | PASS | Consent recorded for KYC verification. |
| DOC_PRESENT_GST | PASS | Gst certificate received. |
| DOC_PRESENT_UDYAM | PASS | Udyam certificate received. |
| DOC_PRESENT_ADDR | PASS | Address proof received. |
| DOC_PRESENT_ID | PASS | Signatory id received. |
| DOC_QUALITY | FAIL (blocker) | Too blurry to read: GST certificate. |
| UDYAM_FORMAT | PASS | Udyam number UDYAM-MH-00-•••1836 looks valid. |
| UDYAM_REGISTRY | PASS | Found in the mock Udyam registry. |
| UDYAM_NAME_MATCH | PASS | Enterprise name matches your other documents (100%). |
| UDYAM_LOCATION | PASS | Udyam city and state match the registry and your GSTIN. |
| ADDR_DATE_FRESH | PASS | Bill is 48 days old (limit 90). |
| ADDR_MATCHES_BUSINESS | PASS | Bill address and name match your business (100%, 100%). |
| ID_FORMAT | PASS | ID number SYN-ID-•••9396 has the expected format. |
| ID_NOT_EXPIRED | PASS | ID valid till 2028-08-03. |
| ID_NAME_BUSINESS | PASS | Signatory ID is issued for this business (100%). |

## K05

**Summary:** Doc Present Udyam: Udyam certificate not uploaded.

**Next action:** Upload your Udyam certificate.

| Check | Result | Detail |
|---|---|---|
| CONSENT_RECORDED | PASS | Consent recorded for KYC verification. |
| DOC_PRESENT_GST | PASS | Gst certificate received. |
| DOC_PRESENT_UDYAM | FAIL (blocker) | Udyam certificate not uploaded. |
| DOC_PRESENT_ADDR | PASS | Address proof received. |
| DOC_PRESENT_ID | PASS | Signatory id received. |
| DOC_QUALITY | PASS | All document images are sharp enough to read. |
| GSTIN_FORMAT | PASS | GSTIN 32••••••••••1Z1 has the right 15-character structure. |
| GSTIN_CHECKSUM | PASS | GSTIN checksum verified. |
| GSTIN_REGISTRY | PASS | Found 32••••••••••1Z1 in the mock GST registry. |
| GSTIN_ACTIVE | PASS | GSTIN status is Active. |
| GST_NAME_MATCH | PASS | Name on the certificate matches the registry (100% similar). |
| GST_ADDR_MATCH | PASS | Address matches the registry (99%). |
| ADDR_DATE_FRESH | PASS | Bill is 34 days old (limit 90). |
| ADDR_MATCHES_BUSINESS | PASS | Bill address and name match your business (100%, 100%). |
| ID_FORMAT | PASS | ID number SYN-ID-•••7234 has the expected format. |
| ID_NOT_EXPIRED | PASS | ID valid till 2029-09-11. |
| ID_NAME_BUSINESS | PASS | Signatory ID is issued for this business (100%). |

## K06

**Summary:** Gstin Checksum: The GSTIN checksum does not match. Gstin Registry: The last character of this GSTIN does not match its checksum.

**Next action:** One character is probably misread - check the GSTIN and correct it.

| Check | Result | Detail |
|---|---|---|
| CONSENT_RECORDED | PASS | Consent recorded for KYC verification. |
| DOC_PRESENT_GST | PASS | Gst certificate received. |
| DOC_PRESENT_UDYAM | PASS | Udyam certificate received. |
| DOC_PRESENT_ADDR | PASS | Address proof received. |
| DOC_PRESENT_ID | PASS | Signatory id received. |
| DOC_QUALITY | PASS | All document images are sharp enough to read. |
| GSTIN_FORMAT | PASS | GSTIN 08••••••••••1Z0 has the right 15-character structure. |
| GSTIN_CHECKSUM | FAIL (blocker) | The GSTIN checksum does not match. |
| GSTIN_REGISTRY | FAIL (blocker) | The last character of this GSTIN does not match its checksum. |
| UDYAM_FORMAT | PASS | Udyam number UDYAM-RJ-00-•••7157 looks valid. |
| UDYAM_REGISTRY | PASS | Found in the mock Udyam registry. |
| UDYAM_NAME_MATCH | PASS | Enterprise name matches your other documents (100%). |
| UDYAM_LOCATION | PASS | Udyam city and state match the registry and your GSTIN. |
| ADDR_DATE_FRESH | PASS | Bill is 34 days old (limit 90). |
| ADDR_MATCHES_BUSINESS | PASS | Bill address and name match your business (100%, 100%). |
| ID_FORMAT | PASS | ID number SYN-ID-•••8354 has the expected format. |
| ID_NOT_EXPIRED | PASS | ID valid till 2028-09-15. |
| ID_NAME_BUSINESS | PASS | Signatory is the proprietor of this business (100% business, 100% name). |

## K07

**Summary:** All checks passed. This application is ready.

| Check | Result | Detail |
|---|---|---|
| CONSENT_RECORDED | PASS | Consent recorded for KYC verification. |
| DOC_PRESENT_GST | PASS | Gst certificate received. |
| DOC_PRESENT_UDYAM | PASS | Udyam certificate received. |
| DOC_PRESENT_ADDR | PASS | Address proof received. |
| DOC_PRESENT_ID | PASS | Signatory id received. |
| DOC_QUALITY | PASS | All document images are sharp enough to read. |
| GSTIN_FORMAT | PASS | GSTIN 07••••••••••1ZT has the right 15-character structure. |
| GSTIN_CHECKSUM | PASS | GSTIN checksum verified. |
| GSTIN_REGISTRY | PASS | Found 07••••••••••1ZT in the mock GST registry. |
| GSTIN_ACTIVE | PASS | GSTIN status is Active. |
| GST_NAME_MATCH | PASS | Name on the certificate matches the registry (100% similar). |
| GST_ADDR_MATCH | PASS | Address matches the registry (100%). |
| UDYAM_FORMAT | PASS | Udyam number UDYAM-DL-00-•••5547 looks valid. |
| UDYAM_REGISTRY | PASS | Found in the mock Udyam registry. |
| UDYAM_NAME_MATCH | PASS | Enterprise name matches your other documents (100%). |
| UDYAM_LOCATION | PASS | Udyam city and state match the registry and your GSTIN. |
| ADDR_DATE_FRESH | PASS | Bill is 10 days old (limit 90). |
| ADDR_MATCHES_BUSINESS | PASS | Bill address and name match your business (100%, 100%). |
| ID_FORMAT | PASS | ID number SYN-ID-•••8237 has the expected format. |
| ID_NOT_EXPIRED | PASS | ID valid till 2030-05-05. |
| ID_NAME_BUSINESS | PASS | Signatory is the proprietor of this business (100% business, 100% name). |

## K08

**Summary:** All checks passed. This application is ready.

| Check | Result | Detail |
|---|---|---|
| CONSENT_RECORDED | PASS | Consent recorded for KYC verification. |
| DOC_PRESENT_GST | PASS | Gst certificate received. |
| DOC_PRESENT_UDYAM | PASS | Udyam certificate received. |
| DOC_PRESENT_ADDR | PASS | Address proof received. |
| DOC_PRESENT_ID | PASS | Signatory id received. |
| DOC_QUALITY | PASS | All document images are sharp enough to read. |
| GSTIN_FORMAT | PASS | GSTIN 24••••••••••1Z3 has the right 15-character structure. |
| GSTIN_CHECKSUM | PASS | GSTIN checksum verified. |
| GSTIN_REGISTRY | PASS | Found 24••••••••••1Z3 in the mock GST registry. |
| GSTIN_ACTIVE | PASS | GSTIN status is Active. |
| GST_NAME_MATCH | PASS | Name on the certificate matches the registry (100% similar). |
| GST_ADDR_MATCH | PASS | Address matches the registry (100%). |
| UDYAM_FORMAT | PASS | Udyam number UDYAM-GJ-00-•••7445 looks valid. |
| UDYAM_REGISTRY | PASS | Found in the mock Udyam registry. |
| UDYAM_NAME_MATCH | PASS | Enterprise name matches your other documents (100%). |
| UDYAM_LOCATION | PASS | Udyam city and state match the registry and your GSTIN. |
| ADDR_DATE_FRESH | PASS | Bill is 50 days old (limit 90). |
| ADDR_MATCHES_BUSINESS | PASS | Bill address and name match your business (100%, 100%). |
| ID_FORMAT | PASS | ID number SYN-ID-•••3148 has the expected format. |
| ID_NOT_EXPIRED | PASS | ID valid till 2027-09-18. |
| ID_NAME_BUSINESS | PASS | Signatory is the proprietor of this business (100% business, 100% name). |

## K09

**Summary:** All checks passed. This application is ready.

| Check | Result | Detail |
|---|---|---|
| CONSENT_RECORDED | PASS | Consent recorded for KYC verification. |
| DOC_PRESENT_GST | PASS | Gst certificate received. |
| DOC_PRESENT_UDYAM | PASS | Udyam certificate received. |
| DOC_PRESENT_ADDR | PASS | Address proof received. |
| DOC_PRESENT_ID | PASS | Signatory id received. |
| DOC_QUALITY | PASS | All document images are sharp enough to read. |
| GSTIN_FORMAT | PASS | GSTIN 37••••••••••1ZB has the right 15-character structure. |
| GSTIN_CHECKSUM | PASS | GSTIN checksum verified. |
| GSTIN_REGISTRY | PASS | Found 37••••••••••1ZB in the mock GST registry. |
| GSTIN_ACTIVE | PASS | GSTIN status is Active. |
| GST_NAME_MATCH | PASS | Name on the certificate matches the registry (100% similar). |
| GST_ADDR_MATCH | PASS | Address matches the registry (100%). |
| UDYAM_FORMAT | PASS | Udyam number UDYAM-AP-00-•••1562 looks valid. |
| UDYAM_REGISTRY | PASS | Found in the mock Udyam registry. |
| UDYAM_NAME_MATCH | PASS | Enterprise name matches your other documents (100%). |
| UDYAM_LOCATION | PASS | Udyam city and state match the registry and your GSTIN. |
| ADDR_DATE_FRESH | PASS | Bill is 5 days old (limit 90). |
| ADDR_MATCHES_BUSINESS | PASS | Bill address and name match your business (100%, 100%). |
| ID_FORMAT | PASS | ID number SYN-ID-•••6040 has the expected format. |
| ID_NOT_EXPIRED | PASS | ID valid till 2027-12-22. |
| ID_NAME_BUSINESS | PASS | Signatory is the proprietor of this business (100% business, 100% name). |

## K10

**Summary:** All checks passed. This application is ready.

| Check | Result | Detail |
|---|---|---|
| CONSENT_RECORDED | PASS | Consent recorded for KYC verification. |
| DOC_PRESENT_GST | PASS | Gst certificate received. |
| DOC_PRESENT_UDYAM | PASS | Udyam certificate received. |
| DOC_PRESENT_ADDR | PASS | Address proof received. |
| DOC_PRESENT_ID | PASS | Signatory id received. |
| DOC_QUALITY | PASS | All document images are sharp enough to read. |
| GSTIN_FORMAT | PASS | GSTIN 27••••••••••1ZL has the right 15-character structure. |
| GSTIN_CHECKSUM | PASS | GSTIN checksum verified. |
| GSTIN_REGISTRY | PASS | Found 27••••••••••1ZL in the mock GST registry. |
| GSTIN_ACTIVE | PASS | GSTIN status is Active. |
| GST_NAME_MATCH | PASS | Name on the certificate matches the registry (100% similar). |
| GST_ADDR_MATCH | PASS | Address matches the registry (100%). |
| UDYAM_FORMAT | PASS | Udyam number UDYAM-MH-00-•••3141 looks valid. |
| UDYAM_REGISTRY | PASS | Found in the mock Udyam registry. |
| UDYAM_NAME_MATCH | PASS | Enterprise name matches your other documents (100%). |
| UDYAM_LOCATION | PASS | Udyam city and state match the registry and your GSTIN. |
| ADDR_DATE_FRESH | PASS | Bill is 27 days old (limit 90). |
| ADDR_MATCHES_BUSINESS | PASS | Bill address and name match your business (100%, 100%). |
| ID_FORMAT | PASS | ID number SYN-ID-•••7542 has the expected format. |
| ID_NOT_EXPIRED | PASS | ID valid till 2029-06-01. |
| ID_NAME_BUSINESS | PASS | Signatory ID is issued for this business (100%). |

## K11

**Summary:** Addr Date Fresh: Address proof is 257 days old (limit 90).

**Next action:** Upload a newer electricity bill (under 90 days old).

| Check | Result | Detail |
|---|---|---|
| CONSENT_RECORDED | PASS | Consent recorded for KYC verification. |
| DOC_PRESENT_GST | PASS | Gst certificate received. |
| DOC_PRESENT_UDYAM | PASS | Udyam certificate received. |
| DOC_PRESENT_ADDR | PASS | Address proof received. |
| DOC_PRESENT_ID | PASS | Signatory id received. |
| DOC_QUALITY | PASS | All document images are sharp enough to read. |
| GSTIN_FORMAT | PASS | GSTIN 03••••••••••1ZZ has the right 15-character structure. |
| GSTIN_CHECKSUM | PASS | GSTIN checksum verified. |
| GSTIN_REGISTRY | PASS | Found 03••••••••••1ZZ in the mock GST registry. |
| GSTIN_ACTIVE | PASS | GSTIN status is Active. |
| GST_NAME_MATCH | PASS | Name on the certificate matches the registry (100% similar). |
| GST_ADDR_MATCH | PASS | Address matches the registry (100%). |
| UDYAM_FORMAT | PASS | Udyam number UDYAM-PB-00-•••9478 looks valid. |
| UDYAM_REGISTRY | PASS | Found in the mock Udyam registry. |
| UDYAM_NAME_MATCH | PASS | Enterprise name matches your other documents (100%). |
| UDYAM_LOCATION | PASS | Udyam city and state match the registry and your GSTIN. |
| ADDR_DATE_FRESH | FAIL (blocker) | Address proof is 257 days old (limit 90). |
| ADDR_MATCHES_BUSINESS | PASS | Bill address and name match your business (100%, 100%). |
| ID_FORMAT | PASS | ID number SYN-ID-•••0312 has the expected format. |
| ID_NOT_EXPIRED | PASS | ID valid till 2028-12-23. |
| ID_NAME_BUSINESS | PASS | Signatory ID is issued for this business (100%). |

## K12

**Summary:** All checks passed. This application is ready.

| Check | Result | Detail |
|---|---|---|
| CONSENT_RECORDED | PASS | Consent recorded for KYC verification. |
| DOC_PRESENT_GST | PASS | Gst certificate received. |
| DOC_PRESENT_UDYAM | PASS | Udyam certificate received. |
| DOC_PRESENT_ADDR | PASS | Address proof received. |
| DOC_PRESENT_ID | PASS | Signatory id received. |
| DOC_QUALITY | PASS | All document images are sharp enough to read. |
| GSTIN_FORMAT | PASS | GSTIN 37••••••••••1ZU has the right 15-character structure. |
| GSTIN_CHECKSUM | PASS | GSTIN checksum verified. |
| GSTIN_REGISTRY | PASS | Found 37••••••••••1ZU in the mock GST registry. |
| GSTIN_ACTIVE | PASS | GSTIN status is Active. |
| GST_NAME_MATCH | PASS | Name on the certificate matches the registry (100% similar). |
| GST_ADDR_MATCH | PASS | Address matches the registry (100%). |
| UDYAM_FORMAT | PASS | Udyam number UDYAM-AP-00-•••6772 looks valid. |
| UDYAM_REGISTRY | PASS | Found in the mock Udyam registry. |
| UDYAM_NAME_MATCH | PASS | Enterprise name matches your other documents (100%). |
| UDYAM_LOCATION | PASS | Udyam city and state match the registry and your GSTIN. |
| ADDR_DATE_FRESH | PASS | Bill is 9 days old (limit 90). |
| ADDR_MATCHES_BUSINESS | PASS | Bill address and name match your business (100%, 100%). |
| ID_FORMAT | PASS | ID number SYN-ID-•••5512 has the expected format. |
| ID_NOT_EXPIRED | PASS | ID valid till 2029-03-03. |
| ID_NAME_BUSINESS | PASS | Signatory is the proprietor of this business (100% business, 100% name). |
