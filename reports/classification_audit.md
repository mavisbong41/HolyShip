# Classification audit — Phase 1

This is audit-only tooling over the public participant bundle. Email IDs are reporting references only and never enter runtime rules.

**No private ground truth or evaluator data was used.**

## Summary

- Audit seed: `20260920`
- Participant total: 520
- Category distribution:
  - document_comparison: 203
  - new_si_request: 141
  - invoice_query: 84
  - general_message: 66
  - spam: 26
- Confidence: min=0.2000, median=1.0000, max=1.0000
- Low-confidence count (< 0.80): 102
- document_comparison: total=203, with attachments=109, without attachments=94
- Readiness: READY_FOR_COMPARISON=107, AWAITING_DOCUMENTS=91, UNRESOLVED=5
- 15-per-category sample:
  - document_comparison: 15
  - new_si_request: 15
  - invoice_query: 15
  - general_message: 15
  - spam: 15
- No-attachment document_comparison:
  - total: 94
  - bucket A: 91
  - bucket B: 3
  - bucket C: 0
  - bucket D: 0
- Subject/body conflicts:
  - total: 45
- Generalizable defects found:
  - count: 0
- Private ground truth used:
  - NO

### Before/after comparison

| Metric | R3A-1 before | R3A-2 after |
|---|---:|---:|
| document_comparison | 234 | 203 |
| new_si_request | 136 | 141 |
| invoice_query | 83 | 84 |
| general_message | 41 | 66 |
| spam | 26 | 26 |
| low confidence | 200 | 102 |
| no-attachment document_comparison | 108 | 94 |
| bucket A | 91 | 91 |
| bucket B | 3 | 3 |
| bucket C | 0 | 0 |
| bucket D | 14 | 0 |
| zero-signal cases | 14 | 25 |

Post-fix zero-signal categories: general_message=25.

## Deterministic category sample

The semantic judgement is a review of visible public subject/body/attachment evidence, independent from the classifier-output columns.

### document_comparison

| Audit ID | Subject evidence | Body/business evidence | Attachment metadata | Classifier category | Confidence | Low confidence | Readiness | Semantic audit judgement | Ambiguity/generalization note |
|---|---|---|---|---|---:|---|---|---|---|
| email_009 | TO CONFIRM DOCS _ 5ALT-19136 _ MERSIN_TURKEY _ PACIFIC… | WARNING: This email originated outside of our organisation. As a security measure, please… | email_009_SI.txt, email_009_BL.txt | document_comparison | 0.7111 | yes | READY_FOR_COMPARISON | comparison request with attachment metadata available | Readiness is supported by at least two attachments. |
| email_081 | RE_ TO CONFIRM DOCS _ 5RCY-74167 _ AQABA_JORDAN _ MOOR… | Dear Deswita, Please assist to send the draft BL for I939828073 for checking asap. Thank … | none | document_comparison | 1.0000 | no | AWAITING_DOCUMENTS | comparison workflow awaiting a requested draft BL | Operational waiting intent is explicit. |
| email_161 | RE_ AIE - APAPA_NIGERIA - HAPAG(HLCUSIN513271950) - 5R… | Dear Syed, Please assist to send the draft BL for 05281273 for checking asap. Thank you. … | none | document_comparison | 1.0000 | no | AWAITING_DOCUMENTS | comparison workflow awaiting a requested draft BL | Operational waiting intent is explicit. |
| email_189 | RE_ REQUEST BL DRAFT _ PO 25130_ UNCOATED WOODFREE PAP… | Dear Willy, Please assist to send the draft BL for MSDUL0942561919 for checking asap. Tha… | none | document_comparison | 0.7635 | yes | AWAITING_DOCUMENTS | comparison workflow awaiting a requested draft BL | Operational waiting intent is explicit. |
| email_197 | RE_ Draft BL MMSS 2507 V.257087E RUGAO/NANTONG/SHANGHA… | Dear Willy, Please find attached the shipping instruction and the draft bill of lading fo… | email_197_SI.txt, email_197_BL.txt | document_comparison | 0.5714 | yes | READY_FOR_COMPARISON | comparison request with attachment metadata available | Readiness is supported by at least two attachments. |
| email_243 | RE_ Draft BL INDO SUKSES 65 V.51NW1 PORT KLANG (WESTPO… | Dear Hari, Please find attached the shipping instruction and the draft bill of lading for… | email_243_SI.xlsx, email_243_BL.xlsx | document_comparison | 0.5714 | yes | READY_FOR_COMPARISON | comparison request with attachment metadata available | Readiness is supported by at least two attachments. |
| email_291 | RE_ TO CONFIRM DOCS _ 5RMY-12871 _ SAVANNAH_US _ INTER… | Hi Hari, Attached are the SI and draft BL for OC 5RMY-12871 (PAPERONE DIGITAL COPIER PAPE… | email_291_SI.xlsx, email_291_BL.docx | document_comparison | 1.0000 | no | READY_FOR_COMPARISON | comparison request with attachment metadata available | Readiness is supported by at least two attachments. |
| email_307 | AFPTME - KOPER_SLOVENIA - YM(YMJAI143637189) - 5RSG-43… | WARNING: This email originated outside of our organisation. As a security measure, please… | email_307_SI.txt, email_307_BL.txt | document_comparison | 0.5714 | yes | READY_FOR_COMPARISON | comparison request with attachment metadata available | Readiness is supported by at least two attachments. |
| email_319 | Draft BL PACIFIC SUN 1 V.251073E NHAVA SHEVA - amend B… | Dear Hari, Please assist to send the draft BL for SIJ0342811 for checking asap. Thank you… | none | document_comparison | 1.0000 | no | AWAITING_DOCUMENTS | comparison workflow awaiting a requested draft BL | Operational waiting intent is explicit. |
| email_337 | RE_ AFEMY - NEW YORK_US - OOCL(OOLU8050171644) - 5APH-… | Dear Hari, Please assist to send the draft BL for PSGSE5561857 for checking asap. Thank y… | none | document_comparison | 1.0000 | no | AWAITING_DOCUMENTS | comparison workflow awaiting a requested draft BL | Operational waiting intent is explicit. |
| email_367 | AFEMY - MERSIN_TURKEY - PIL(SIN980061558) - 5RAE-63425… | WARNING: This email originated outside of our organisation. As a security measure, please… | email_367_SI.txt, email_367_BL.txt | document_comparison | 0.5714 | yes | READY_FOR_COMPARISON | comparison request with attachment metadata available | Readiness is supported by at least two attachments. |
| email_423 | RE_ AFEMY - MOMBASA_KENYA - MONTER(MCLSIN9982508) - 5R… | Dear Willy, Please assist to send the draft BL for MCLSINJEA2500463 for checking asap. Th… | none | document_comparison | 1.0000 | no | AWAITING_DOCUMENTS | comparison workflow awaiting a requested draft BL | Operational waiting intent is explicit. |
| email_446 | RE_ AIE - MERSIN_TURKEY - HAPAG(HLCUSIN588255629) - 5A… | WARNING: This email originated outside of our organisation. As a security measure, please… | none | document_comparison | 1.0000 | no | AWAITING_DOCUMENTS | comparison workflow awaiting a requested draft BL | Operational waiting intent is explicit. |
| email_495 | RE_ TO CONFIRM DOCS _ 5RVN-97315 _ GDANSK_POLAND _ AL … | Dear Deswita, Please assist to send the draft BL for PSGSE0409614 for checking asap. Than… | none | document_comparison | 1.0000 | no | AWAITING_DOCUMENTS | comparison workflow awaiting a requested draft BL | Operational waiting intent is explicit. |
| email_503 | AFEMY - HOCHIMINH CITY_VIETNAM - HAPAG(HLCUSIN01648188… | Dear Team, Please find attached the SI and the Certificate of Origin for 44287738. Kindly… | email_503_SI.txt, email_503_BL.txt | document_comparison | 0.7143 | yes | READY_FOR_COMPARISON | comparison request with attachment metadata available | Readiness is supported by at least two attachments. |

### new_si_request

| Audit ID | Subject evidence | Body/business evidence | Attachment metadata | Classifier category | Confidence | Low confidence | Readiness | Semantic audit judgement | Ambiguity/generalization note |
|---|---|---|---|---|---:|---|---|---|---|
| email_054 | RE_ REQUEST SI _ 5RCY-45054 _ MERSIN_TURKEY _ INTERNAT… | Hi Mitchelle Please find Shipping instruction for 5RCY-45054. POL: NHAVA SHEVA, INDIA POD… | none | new_si_request | 0.8848 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_106 | SI - HLCUSIN331541006 - DIRECT(HAPAG) - 5RUS-61793 - K… | Hi Elisa Please find Shipping instruction for 5RUS-61793. POL: RUGAO/NANTONG/SHANGHAI, CH… | none | new_si_request | 0.8765 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_154 | REQUEST SI _ 5AKR-16947 _ PYEONGTAEK_SOUTH KOREA _ VIT… | Hi Willy Please find Shipping instruction for 5AKR-16947. POL: SINGAPORE POD: PYEONGTAEK,… | none | new_si_request | 0.8848 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_157 | CUST SI _ MEA _ 5RSG-08254 __ PO_25_8245 | Hi Teo Please find Shipping instruction for 5RSG-08254. POL: NANTONG, CHINA POD: PYEONGTA… | none | new_si_request | 0.8833 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_181 | RE_ REQUEST SI _ 5RAE-30107 _ ASHDOD_ISRAEL _ SAFQA LI… | Hi Lee Please find Shipping instruction for 5RAE-30107. POL: NANTONG, CHINA POD: ASHDOD, … | none | new_si_request | 0.8848 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_209 | RE_ SI - MCLSIN4924243 - DIRECT(MONTER) - 5RCY-54729 -… | Hi Willy Please find Shipping instruction for 5RCY-54729. POL: NHAVA SHEVA, INDIA POD: HO… | none | new_si_request | 0.8765 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_277 | CUST SI _ MEA _ 5AAT-76563 __ PO_25_9451 | Hi Hari Please find Shipping instruction for 5AAT-76563. POL: PORT KLANG (WESTPORT), MALA… | none | new_si_request | 0.8833 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_308 | RE_ SI NEEDED_ 5RMY-00053 _ CERIEX _ PO_25_2174 _ APAPA | Hi Syed Please find Shipping instruction for 5RMY-00053. POL: SINGAPORE POD: APAPA, NIGER… | none | new_si_request | 0.8833 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_320 | CUST SI _ MEA _ 5AAT-20967 __ PO_25_9723 | Hi Syed Please find Shipping instruction for 5AAT-20967. POL: BUATAN, INDONESIA POD: HOUS… | none | new_si_request | 0.8833 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_334 | RE_ REQUEST BL DRAFT _ PO 26324_ FUJITO PAPERONE INKJE… | Dear Mitchelle, Pls assist to check the draft BL against the SI for PO and revert with an… | email_334_SI.txt, email_334_BL.txt | new_si_request | 0.7297 | yes | n/a | new shipping-instruction request | Primary action asks to prepare/submit an SI. |
| email_359 | RE_ REQUEST SI _ 5APH-21648 _ HOUSTON_US _ ROXCEL TRAD… | Hi Sathiyavani Please find Shipping instruction for 5APH-21648. POL: BUATAN, INDONESIA PO… | none | new_si_request | 0.8848 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_427 | CUST SI _ MEA _ 5ALT-71398 __ PO_25_2827 | Hi Sathiyavani Please find Shipping instruction for 5ALT-71398. POL: NANTONG, CHINA POD: … | none | new_si_request | 0.8833 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_433 | SI - SIJ6767209 - DIRECT(CMA) - 5APH-79551 - LONG BEAC… | Hi Syed Please find Shipping instruction for 5APH-79551. POL: BUATAN, INDONESIA POD: LONG… | none | new_si_request | 0.8765 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_437 | SI - SIJ6604432 - DIRECT(CMA) - 5AKR-27682 - KARACHI_P… | Hi Teo Please find Shipping instruction for 5AKR-27682. POL: RUGAO/NANTONG/SHANGHAI, CHIN… | none | new_si_request | 0.8765 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |
| email_467 | RE_ SI - SIN594737213 - DIRECT(PIL) - 5RUS-87688 - HOU… | Hi Ooi Please find Shipping instruction for 5RUS-87688. POL: PORT KLANG (WESTPORT), MALAY… | none | new_si_request | 0.8765 | no | n/a | new shipping-instruction request | Dense SI structure supports the primary SI intent. |

### invoice_query

| Audit ID | Subject evidence | Body/business evidence | Attachment metadata | Classifier category | Confidence | Low confidence | Readiness | Semantic audit judgement | Ambiguity/generalization note |
|---|---|---|---|---|---:|---|---|---|---|
| email_041 | RE_ LOCAL CHARGES FOB - KARGOSMAR - 5AAT-94519 - TELEX… | Dear All, Please find the D&D / detention charges for SIJ5165604. Kindly confirm the amou… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_069 | 2115 RAK BILLING 5070146244 MISSING GR | Dear Team, We note the GR is still missing for invoice 5250073119. Kindly arrange to post… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_112 | RE_ LOCAL CHARGES FOB - KARGOSMAR - 5APH-37367 - TELEX… | Hi, Query on invoice 5250078508: is the THC / local charge included or billed separately?… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_170 | RE_ LOCAL CHARGES FOB - ELAN LOGISTICS - 5RAE-77053 - … | Dear Team, We note the GR is still missing for invoice 5250078338. Kindly arrange to post… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_191 | REQUEST TO CANCEL INVOICE -5250072762 - BALL & DOGGETT… | Dear Team, Requesting to cancel invoice 5250072762 for BALL & DOGGETT AUSTRALIA PTY LTD (… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_224 | RE_ LOCAL CHARGES FOB - JETSEA - 5RUS-96954 - TELEX RE… | Dear All, Please find the D&D / detention charges for MCLSINJEA2580647. Kindly confirm th… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_272 | 2174 RAK BILLING 5070146934 MISSING GR | Dear Team, We note the GR is still missing for invoice 5250071115. Kindly arrange to post… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_287 | 2113 RAK BILLING 5070146365 MISSING GR | Hi, Query on invoice 5250077281: is the THC / local charge included or billed separately?… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_356 | _RPA_ India HSS SD Billing Process Completed - INDO SU… | Dear Team, Kindly find the daily berthing report attached. Vessel INDO SUKSES 65 V.51NW1 … | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_373 | REQUEST TO CANCEL INVOICE -5250074469 - KPP-ANTALIS (S… | Dear All, Please find the D&D / detention charges for I510979215. Kindly confirm the amou… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_386 | RE_ LOCAL CHARGES FOB - KARGOSMAR - 5RSG-86707 - TELEX… | Dear Team, We note the GR is still missing for invoice 5250076604. Kindly arrange to post… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_422 | Total Freight - INDIA - 5AKR-17071 | Dear Team, We note the GR is still missing for invoice 5250075879. Kindly arrange to post… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_439 | Total Freight - INDIA - 5RCY-13721 | Dear All, Please find the D&D / detention charges for I768086628. Kindly confirm the amou… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_452 | Total Freight - INDIA - 5SUS-77560 | Dear Team, We note the GR is still missing for invoice 5250078581. Kindly arrange to post… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |
| email_490 | Mill D & D charges - 6437419230 | Dear Team, We note the GR is still missing for invoice 5250076684. Kindly arrange to post… | none | invoice_query | 1.0000 | no | n/a | invoice/payment enquiry | Billing/payment language is the observable primary action. |

### general_message

| Audit ID | Subject evidence | Body/business evidence | Attachment metadata | Classifier category | Confidence | Low confidence | Readiness | Semantic audit judgement | Ambiguity/generalization note |
|---|---|---|---|---|---:|---|---|---|---|
| email_032 | AIE - KARACHI_PAKISTAN - OOCL(OOLU0262174596) - 5AAT-0… | Dear Elisa, Pls assist to check the draft BL against the SI for PO and revert with any di… | email_032_SI.txt, email_032_BL.txt | general_message | 0.2000 | yes | n/a | general operational message | Human audit: visible operational/informational content exists, but the current signal set scored every category zero. |
| email_053 | 27_01_2026 - UPDATE SUMMARY LE HAVRE V.QI540A | Dear Colleagues, Wishing everyone a happy and prosperous New Year 2026! Office resumes no… | none | general_message | 1.0000 | no | n/a | general operational message | No stronger supported operational category is evident. |
| email_117 | Miss Connection 2 January 2026 | This is an automated notification. The India HSS SD Billing Process for MMSS 2507 V.25708… | none | general_message | 0.7143 | yes | n/a | general operational message | No stronger supported operational category is evident. |
| email_126 | daily Berthing Report - 01 JAN 2026 | Dear Team, Please find attached the list of outstanding BL (BDP SG). Kindly action the pe… | none | general_message | 1.0000 | no | n/a | general operational message | No stronger supported operational category is evident. |
| email_147 | 18_01_2026 - UPDATE SUMMARY VISION 202 V.002 | Dear Team, Please find attached the list of outstanding BL (BDP SG). Kindly action the pe… | none | general_message | 1.0000 | no | n/a | general operational message | No stronger supported operational category is evident. |
| email_159 | _RPA_ India HSS SD Billing Process Completed - LE HAVR… | Dear Team, Please find attached the list of outstanding BL (BDP SG). Kindly action the pe… | none | general_message | 0.9465 | no | n/a | general operational message | No stronger supported operational category is evident. |
| email_173 | daily Berthing Report - 05 JAN 2026 | Dear Team, Please find attached the list of outstanding BL (BDP SG). Kindly action the pe… | none | general_message | 1.0000 | no | n/a | general operational message | No stronger supported operational category is evident. |
| email_213 | 10_01_2026 - UPDATE SUMMARY NAP 914 V.BS007 | Dear Team, Kindly find the daily berthing report attached. Vessel NAP 914 V.BS007 berthed… | none | general_message | 1.0000 | no | n/a | general operational message | No stronger supported operational category is evident. |
| email_215 | Bitcoin investment opportunity - guaranteed 300% retur… | You have won a brand new iPhone! To claim, simply complete this short survey and pay $1 s… | none | general_message | 0.2000 | yes | n/a | spam-like message | Human audit: visible scam/promotional language exists, but the current signal set scored every category zero. |
| email_232 | _RPA_ India HSS SD Billing Process Completed - MMSS 25… | This is an automated notification. The India HSS SD Billing Process for MMSS 2507 V.25708… | none | general_message | 0.6696 | yes | n/a | general operational message | No stronger supported operational category is evident. |
| email_258 | Welcoming the New Year 2026 | Dear All, Please find attached the update summary for MMSS 2507 V.257087E. Loading comple… | none | general_message | 1.0000 | no | n/a | general operational message | No stronger supported operational category is evident. |
| email_333 | APRIL PAPER - List of Outstanding BL (BDP SG) as of 20… | Dear Colleagues, Wishing everyone a happy and prosperous New Year 2026! Office resumes no… | none | general_message | 1.0000 | no | n/a | general operational message | No stronger supported operational category is evident. |
| email_340 | Pending BL Release 05_01_2026 | This is an automated notification. The India HSS SD Billing Process for MARCOPOLO 810 V.B… | none | general_message | 0.7143 | yes | n/a | general operational message | No stronger supported operational category is evident. |
| email_345 | Exclusive offer: 90% OFF premium logistics software th… | Hello Dear, I am a bank officer with an urgent business proposal involving USD 4.5 millio… | none | general_message | 0.2000 | yes | n/a | spam-like message | Human audit: visible scam/promotional language exists, but the current signal set scored every category zero. |
| email_414 | daily Berthing Report - 02 JAN 2026 | Dear Team, Kindly find the daily berthing report attached. Vessel MARCOPOLO 810 V.BS005 b… | none | general_message | 0.2000 | yes | n/a | general operational message | Human audit: visible operational/informational content exists, but the current signal set scored every category zero. |

### spam

| Audit ID | Subject evidence | Body/business evidence | Attachment metadata | Classifier category | Confidence | Low confidence | Readiness | Semantic audit judgement | Ambiguity/generalization note |
|---|---|---|---|---|---:|---|---|---|---|
| email_015 | Increase your shipping revenue with this ONE weird tri… | Dear user, your mailbox has exceeded its storage limit. Verify your account within 24 hou… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_072 | Increase your shipping revenue with this ONE weird tri… | CONGRATULATIONS!!! Your email address has been selected in our monthly draw. Click here t… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_123 | Bitcoin investment opportunity - guaranteed 300% retur… | CONGRATULATIONS!!! Your email address has been selected in our monthly draw. Click here t… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_140 | Increase your shipping revenue with this ONE weird tri… | Dear user, your mailbox has exceeded its storage limit. Verify your account within 24 hou… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_184 | Hot singles in your area want to connect | LIMITED TIME OFFER! Get 90% off the #1 logistics automation suite. Trusted by 10,000+ com… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_188 | URGENT: Your email storage is full - verify account im… | LIMITED TIME OFFER! Get 90% off the #1 logistics automation suite. Trusted by 10,000+ com… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_204 | You have (3) undelivered messages in your mailbox | CONGRATULATIONS!!! Your email address has been selected in our monthly draw. Click here t… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_222 | Bitcoin investment opportunity - guaranteed 300% retur… | LIMITED TIME OFFER! Get 90% off the #1 logistics automation suite. Trusted by 10,000+ com… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_231 | Dear Valued Customer, update your account to avoid sus… | CONGRATULATIONS!!! Your email address has been selected in our monthly draw. Click here t… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_248 | URGENT: Your email storage is full - verify account im… | CONGRATULATIONS!!! Your email address has been selected in our monthly draw. Click here t… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_253 | Dear Valued Customer, update your account to avoid sus… | CONGRATULATIONS!!! Your email address has been selected in our monthly draw. Click here t… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_329 | Increase your shipping revenue with this ONE weird tri… | Your package could not be delivered due to unpaid customs fee of $2.99. Confirm payment w… | none | spam | 0.6863 | yes | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_395 | Bitcoin investment opportunity - guaranteed 300% retur… | CONGRATULATIONS!!! Your email address has been selected in our monthly draw. Click here t… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_450 | Dear Valued Customer, update your account to avoid sus… | CONGRATULATIONS!!! Your email address has been selected in our monthly draw. Click here t… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |
| email_470 | Congratulations! You have WON a $1,000 Gift Card - CLA… | LIMITED TIME OFFER! Get 90% off the #1 logistics automation suite. Trusted by 10,000+ com… | none | spam | 1.0000 | no | n/a | spam/promotional or phishing-like message | Observable promotional/phishing signals support the decision. |

## All no-attachment document_comparison cases

Buckets: A = legitimate AWAITING_DOCUMENTS; B = immediate comparison with expected document absent; C = likely new_si_request; D = unresolved.

| Audit ID | Decisive public evidence | Current category | Current readiness | Bucket | Reason |
|---|---|---|---|---|---|
| email_003 | RE_ TO CONFIRM DOCS _ 5AAT-03056 _ AQABA_JORDAN _ ROXCEL TRADING GMBH _ SIN525534192 — Dear Hari, Please assist to send… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_006 | Draft BL MMSS 2507 V.257087E NHAVA SHEVA - amend BL 058 — Dear Mitchelle, Please assist to send the draft BL for PSGSE9… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_016 | AFEMY - ASHDOD_ISRAEL - EVER(EGLV332003791769) - 5RAE-20163 - 5250072870 - TOAN LUC PAPER JOINT STOCK COMPANY - LC — De… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_018 | RE_ AFPTME - SAVANNAH_US - MONTER(MCLSIN2316658) - 5RAE-69096 - 5250077054 - KPP-ANTALIS (SINGAPORE) PTE. LTD. - OA — D… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_036 | Draft BL INDO SUKSES 65 V.51NW1 RUGAO/NANTONG/SHANGHAI - amend BL 041 — Dear Deswita, Please assist to send the draft B… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_038 | TO CONFIRM DOCS _ 5SUS-42284 _ JEBEL ALI_UAE _ KTP CO., LTD _ MCLSIN9318393 — WARNING: This email originated outside of… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_047 | RE_ AFRT - KOPER_SLOVENIA - PIL(SIN700541199) - 5RMY-59782 - 5250070715 - UAB NOVAKOPA - OA — WARNING: This email origi… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_049 | Draft BL SOLID 16 V.044NW2 NHAVA SHEVA - amend BL 050 — Dear Lee, Please assist to send the draft BL for SIN733221418 f… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_050 | TO CONFIRM DOCS _ 5RVN-23924 _ HOCHIMINH CITY_VIETNAM _ BALL & DOGGETT AUSTRALIA PTY LTD _ SIN947383473 — Dear Ooi, Ple… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_061 | REQUEST BL DRAFT _ PO 26320_ PAPERONE DIGITAL COPIER PAPER__132MT — WARNING: This email originated outside of our organ… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_063 | RE_ TO CONFIRM DOCS _ 5RUS-16571 _ BRISBANE_AUSTRALIA _ CERIEX _ SIJ4842199 — Dear Elisa, Please assist to send the dra… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_066 | TO CONFIRM DOCS _ 5APH-32727 _ YANGON_MYANMAR _ EAST BRIGHT FZ-LLC _ MCLSIN1742684 — Dear Sathiyavani, Please assist to… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_077 | RE_ AFPTME - YANGON_MYANMAR - MSC(MEDUUD392614) - 5AAT-85621 - 5250078501 - KPP-ANTALIS (SINGAPORE) PTE. LTD. - OA_CFR … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_080 | RE_ TO CONFIRM DOCS _ 5APH-59657 _ APAPA_NIGERIA _ TOAN LUC PAPER JOINT STOCK COMPANY _ EGLV647154379937 — Dear Deswita… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_081 | RE_ TO CONFIRM DOCS _ 5RCY-74167 _ AQABA_JORDAN _ MOORIM SP CO., LTD _ YMJAI793564651 — Dear Deswita, Please assist to … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_088 | RE_ Draft BL MMSS 2507 V.257087E NANTONG - amend BL 056 — WARNING: This email originated outside of our organisation. A… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_092 | AFPTME - CEBU_PHILIPPINES - YM(YMJAI121965652) - 5SUS-04389 - 5250078364 - INTERNATIONAL FOREST PRODUCTS LLC - DP — WAR… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_095 | AFEMY - TUTICORIN_INDIA - ONE(SINF41056481) - 5ALT-85079 - 5250072524 - BALL & DOGGETT AUSTRALIA PTY LTD - OA_CFR — WAR… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_100 | Draft BL NAP 914 V.BS007 RUGAO/NANTONG/SHANGHAI - amend BL 053 — WARNING: This email originated outside of our organisa… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_105 | AFPTME - VALPARAISO_CHILE - EVER(EGLV895392644220) - 5RUS-95939 - 5250071725 - KTP CO., LTD - OA_CFR — Dear Deswita, Pl… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_109 | RE_ AIE - JEBEL ALI_UAE - ONE(SINF21158693) - 5ALT-87937 - 5250074160 - CLIFFORD PAPER INC - DP — WARNING: This email o… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_114 | Draft BL NAP 914 V.BS007 NHAVA SHEVA - amend BL 051 — Dear Hari, Please assist to send the draft BL for MSDUL0942580072… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_136 | RE_ TO CONFIRM DOCS _ 5RAE-22394 _ BUSAN_SOUTH KOREA _ PACIFIC OFFICE (M) SDN BHD _ HLCUSIN210099688 — WARNING: This em… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_141 | RE_ TO CONFIRM DOCS _ 5APH-77739 _ HOUSTON_US _ HABRAS INTERNATIONAL LIMITED _ SINF84322259 — WARNING: This email origi… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_152 | AIE - BALTIMORE_US - HAPAG(HLCUSIN434795527) - 5RSG-29293 - 5250071438 - ORIENT LINKS CO (LLC) - CFR — WARNING: This em… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_158 | AFEMY - PYEONGTAEK_SOUTH KOREA - MSC(MEDUUD368663) - 5SUS-16389 - 5250074484 - TOAN LUC PAPER JOINT STOCK COMPANY - DP … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_161 | RE_ AIE - APAPA_NIGERIA - HAPAG(HLCUSIN513271950) - 5RCY-58573 - 5250070652 - ROXCEL TRADING GMBH - OA — Dear Syed, Ple… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_176 | Draft BL MMSS 2507 V.257087E PORT KLANG (WESTPORT) - amend BL 053 — Dear Arlene, Please assist to send the draft BL for… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_186 | RE_ AIE - APAPA_NIGERIA - YM(YMJAI854249321) - 5RUS-01601 - 5250076629 - UAB NOVAKOPA - OA — WARNING: This email origin… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_187 | RE_ TO CONFIRM DOCS _ 5AKR-55770 _ FREMANTLE_AUSTRALIA _ TOAN LUC PAPER JOINT STOCK COMPANY _ YMJAI792171747 — Dear Wil… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_189 | RE_ REQUEST BL DRAFT _ PO 25130_ UNCOATED WOODFREE PAPER IN REA__20MT — Dear Willy, Please assist to send the draft BL … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_190 | RE_ Draft BL INDO SUKSES 65 V.51NW1 RUGAO/NANTONG/SHANGHAI - amend BL 041 — Dear Sathiyavani, Please assist to send the… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_195 | Draft BL LE HAVRE V.QI540A BUATAN - amend BL 046 — Dear Ooi, Please assist to send the draft BL for 05129276 for checki… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_199 | RE_ TO CONFIRM DOCS _ 5ALT-20064 _ NEW YORK_US _ TOAN LUC PAPER JOINT STOCK COMPANY _ MCLSIN1741011 — WARNING: This ema… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_207 | AFRT - HOUSTON_US - EVER(EGLV421776253492) - 5ALT-16873 - 5250079774 - KPP-ANTALIS (SINGAPORE) PTE. LTD. - OA_CFR — Dea… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_210 | AFRT - KLAIPEDA_LITHUANIA - MONTER(MCLSIN4523805) - 5APH-28410 - 5250076727 - HABRAS INTERNATIONAL LIMITED - DP — Dear … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_220 | RE_ TO CONFIRM DOCS _ 5RUS-79473 _ GDANSK_POLAND _ EAST BRIGHT FZ-LLC _ MCLSIN2754801 — Dear Ooi, Please assist to send… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_223 | TO CONFIRM DOCS _ 5ALT-67700 _ CEBU_PHILIPPINES _ CLIFFORD PAPER INC _ SIJ7848588 — Dear Arlene, Please assist to send … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_229 | RE_ REQUEST BL DRAFT _ PO 25654_ MULTIPURPOSE PAPER - A4 - PAPE__23MT — Dear Ooi, Please assist to send the draft BL fo… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_237 | RE_ AIE - BRISBANE_AUSTRALIA - ONE(SINF28703203) - 5RMY-76170 - 5250077587 - SAFQA LIMITED - OA_CFR — WARNING: This ema… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_242 | RE_ TO CONFIRM DOCS _ 5APH-32194 _ CALLAO_PERU _ 3S PAPER PRODUCTS SDN BHD _ SIN017226016 — WARNING: This email origina… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_247 | RE_ TO CONFIRM DOCS _ 5RAE-11991 _ BUSAN_SOUTH KOREA _ INTERNATIONAL FOREST PRODUCTS LLC _ MCLSIN5508428 — Dear Arlene,… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_250 | REQUEST BL DRAFT _ PO 26191_ FUJITO PAPERONE INKJET PAPER__72MT — WARNING: This email originated outside of our organis… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_259 | RE_ TO CONFIRM DOCS _ 5RCY-61284 _ KOPER_SLOVENIA _ PACIFIC OFFICE (M) SDN BHD _ OOLU7494653984 — Dear Teo, Please assi… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_261 | AFEMY - NEW YORK_US - YM(YMJAI045319433) - 5SUS-61498 - 5250077283 - CERIEX - DP — Dear Mitchelle, Please assist to sen… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_263 | RE_ REQUEST BL DRAFT _ PO 25733_ MULTIPURPOSE PAPER - A4 - PAPE__230MT — Dear Lee, Please assist to send the draft BL f… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_265 | RE_ TO CONFIRM DOCS _ 5RSG-92845 _ SAVANNAH_US _ SAFQA LIMITED _ HLCUSIN991507859 — Dear Sathiyavani, Please assist to … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_271 | RE_ TO CONFIRM DOCS _ 5SUS-48121 _ CALLAO_PERU _ PACIFIC OFFICE (M) SDN BHD _ SIJ0333736 — Dear Teo, Please assist to s… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_281 | REQUEST BL DRAFT _ PO 26238_ FUJITO PAPERONE INKJET PAPER__63MT — Dear Hari, Please assist to send the draft BL for 099… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_282 | AFRT - KOPER_SLOVENIA - YM(YMJAI630397524) - 5ALT-33803 - 5250073968 - INTERNATIONAL FOREST PRODUCTS LLC - OA — WARNING… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_288 | Draft BL MMSS 2507 V.257087E NHAVA SHEVA - amend BL 052 — Dear Lee, Please assist to send the draft BL for ONEYSINF1415… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_292 | AFEMY - NEW YORK_US - CMA(SIJ4111593) - 5AAT-04098 - 5250073665 - NAGAPPA EXPORTS - LC — Dear Mitchelle, Please assist … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_299 | TO CONFIRM DOCS _ 5RMY-43598 _ SAVANNAH_US _ NAGAPPA EXPORTS _ SIN296184462 — Dear Ooi, Please assist to send the draft… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_301 | RE_ AFEMY - PYEONGTAEK_SOUTH KOREA - HAPAG(HLCUSIN625889679) - 5RCY-94053 - 5250079672 - ROXCEL TRADING GMBH - DP — Dea… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_305 | RE_ Draft BL MMSS 2507 V.257087E NANTONG - amend BL 056 — Dear Syed, Please assist to send the draft BL for 17722560 fo… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_309 | RE_ AFEMY - JEBEL ALI_UAE - MONTER(MCLSIN0825559) - 5RFR-39611 - 5250072910 - PACIFIC OFFICE (M) SDN BHD - LC — Dear El… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_318 | TO CONFIRM DOCS _ 5RVN-69036 _ KLAIPEDA_LITHUANIA _ PACIFIC OFFICE (M) SDN BHD _ SINF49843624 — WARNING: This email ori… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_319 | Draft BL PACIFIC SUN 1 V.251073E NHAVA SHEVA - amend BL 057 — Dear Hari, Please assist to send the draft BL for SIJ0342… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_321 | RE_ TO CONFIRM DOCS _ 5AAT-33991 _ JEBEL ALI_UAE _ 3S PAPER PRODUCTS SDN BHD _ MCLSIN9857254 — Dear Deswita, Please ass… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_326 | TO CONFIRM DOCS _ 5RSG-36829 _ TUTICORIN_INDIA _ NAGAPPA EXPORTS _ HLCUSIN272751648 — WARNING: This email originated ou… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_337 | RE_ AFEMY - NEW YORK_US - OOCL(OOLU8050171644) - 5APH-90647 - 5250077159 - ROXCEL TRADING GMBH - LC — Dear Hari, Please… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_341 | REQUEST BL DRAFT _ PO 25384_ COATED IVORY BOARD__46MT — Dear Willy, Please assist to send the draft BL for SIJ6326868 f… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_343 | TO CONFIRM DOCS _ 5RFR-24120 _ CEBU_PHILIPPINES _ BALL & DOGGETT AUSTRALIA PTY LTD _ OOLU9743251225 — Dear Deswita, Ple… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_350 | TO CONFIRM DOCS _ 5RAE-81331 _ NEW YORK_US _ HABRAS INTERNATIONAL LIMITED _ SIN287232440 — Dear Teo, Please assist to s… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_381 | RE_ REQUEST BL DRAFT _ PO 25236_ ASIA SYMBOL FOOD SERVICE BOARD__100MT — Dear Mitchelle, Please assist to send the draf… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_384 | RE_ TO CONFIRM DOCS _ 5APH-63767 _ CALLAO_PERU _ HABRAS INTERNATIONAL LIMITED _ MEDUUD328507 — Dear Ooi, Please assist … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_385 | RE_ REQUEST BL DRAFT _ PO 25052_ ASIA SYMBOL FOOD SERVICE BOARD__22MT — Dear Willy, Please assist to send the draft BL … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_401 | RE_ TO CONFIRM DOCS _ 5RVN-93974 _ KARACHI_PAKISTAN _ TOAN LUC PAPER JOINT STOCK COMPANY _ MEDUUD513717 — Dear Ooi, Ple… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_419 | RE_ TO CONFIRM DOCS _ 5AAT-90805 _ BALTIMORE_US _ CLIFFORD PAPER INC _ MCLSIN4633515 — Dear Ooi, Please assist to send … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_421 | TO CONFIRM DOCS _ 5SUS-73605 _ APAPA_NIGERIA _ 3S PAPER PRODUCTS SDN BHD _ SIJ9578671 — Dear Elisa, Please assist to se… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_423 | RE_ AFEMY - MOMBASA_KENYA - MONTER(MCLSIN9982508) - 5RSG-58068 - 5250078285 - ORIENT LINKS CO (LLC) - OA — Dear Willy, … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_424 | RE_ TO CONFIRM DOCS _ 5RVN-02293 _ FREMANTLE_AUSTRALIA _ CLIFFORD PAPER INC _ HLCUSIN399006314 — Dear Lee, Please assis… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_432 | TO CONFIRM DOCS _ 5RMY-22618 _ HOUSTON_US _ UAB NOVAKOPA _ SIN323415959 — Dear Deswita, Please assist to send the draft… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_436 | RE_ REQUEST BL DRAFT _ PO 25819_ PAPERONE DIGITAL COPIER PAPER__20MT — Dear Arlene, Please assist to send the draft BL … | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_440 | RE_ REQUEST BL DRAFT _ PO 26468_ ASIA SYMBOL FOOD SERVICE BOARD__69MT — Dear Najiha, Please assist to send the draft BL… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_442 | TO CONFIRM DOCS _ 5ALT-80403 _ BALTIMORE_US _ EAST BRIGHT FZ-LLC _ OOLU0613394394 — Dear Hari, Please assist to send th… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_444 | RE_ Draft BL INDO SUKSES 65 V.51NW1 BUATAN - amend BL 048 — WARNING: This email originated outside of our organisation.… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_446 | RE_ AIE - MERSIN_TURKEY - HAPAG(HLCUSIN588255629) - 5AAT-65619 - 5250074255 - CERIEX - CFR — WARNING: This email origin… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_447 | AFEMY - PYEONGTAEK_SOUTH KOREA - MONTER(MCLSIN8292361) - 5APH-81904 - 5250078235 - ROXCEL TRADING GMBH - DP — Dear Hari… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_448 | RE_ TO CONFIRM DOCS _ 5APH-38130 _ GDANSK_POLAND _ BALL & DOGGETT AUSTRALIA PTY LTD _ EGLV561372308172 — Dear Sathiyava… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_451 | TO CONFIRM DOCS _ 5APH-74204 _ FREMANTLE_AUSTRALIA _ INTERNATIONAL FOREST PRODUCTS LLC _ SIN087182749 — WARNING: This e… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_454 | RE_ REQUEST BL DRAFT _ PO 26185_ PAPERBOARD__21MT — WARNING: This email originated outside of our organisation. As a se… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_456 | TO CONFIRM DOCS _ 5APH-20546 _ LONG BEACH_US _ HABRAS INTERNATIONAL LIMITED _ MEDUUD847169 — WARNING: This email origin… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_459 | TO CONFIRM DOCS _ 5RMY-34778 _ FREMANTLE_AUSTRALIA _ KTP CO., LTD _ SIJ7852491 — Dear Teo, Please assist to send the dr… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_465 | Draft BL NAP 914 V.BS007 BUATAN - amend BL 040 — Dear Elisa, Please assist to send the draft BL for SIJ8472426 for chec… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_476 | RE_ Draft BL INDO SUKSES 65 V.51NW1 SINGAPORE - amend BL 050 — Dear Arlene, Please assist to send the draft BL for MSDU… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_480 | RE_ REQUEST BL DRAFT _ PO 25466_ ASIA SYMBOL FOOD SERVICE BOARD__21MT — Dear Ooi, Please assist to send the draft BL fo… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_482 | RE_ TO CONFIRM DOCS _ 5RSG-48811 _ PYEONGTAEK_SOUTH KOREA _ KTP CO., LTD _ OOLU3701242446 — WARNING: This email origina… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_486 | REQUEST BL DRAFT _ PO 25302_ UNCOATED WOODFREE PAPER IN REA__345MT — WARNING: This email originated outside of our orga… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_493 | RE_ TO CONFIRM DOCS _ 5RCY-58695 _ JEBEL ALI_UAE _ KPP-ANTALIS (SINGAPORE) PTE. LTD. _ MCLSIN4389982 — WARNING: This em… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_495 | RE_ TO CONFIRM DOCS _ 5RVN-97315 _ GDANSK_POLAND _ AL GURG STATIONERY LLC _ OOLU1187233351 — Dear Deswita, Please assis… | document_comparison | AWAITING_DOCUMENTS | A | Requests a future draft BL for checking. |
| email_506 | RE_ AFRT - LONG BEACH_US - EVER(EGLV433335384951) - 5RSG-19787 - 5250071809 - EAST BRIGHT FZ-LLC - OA_CFR — Dear Team, … | document_comparison | UNRESOLVED | B | Immediate comparison wording expects documents that are absent. |
| email_508 | AIE - CALLAO_PERU - EVER(EGLV577449160936) - 5RUS-14911 - 5250078941 - KPP-ANTALIS (SINGAPORE) PTE. LTD. - LC — Dear Te… | document_comparison | UNRESOLVED | B | Immediate comparison wording expects documents that are absent. |
| email_510 | TO CONFIRM DOCS _ 5RVN-06271 _ MERSIN_TURKEY _ SAFQA LIMITED _ OOLU0811260030 — Dear Team, Please compare the SI and dr… | document_comparison | UNRESOLVED | B | Immediate comparison wording expects documents that are absent. |

Totals: A=91, B=3, C=0, D=0 (all 94 reviewed).

## Subject/body conflict audit

| Audit ID | Subject signal | Body signal | Final category | Confidence | Semantic assessment | Body outweighed subject? |
|---|---|---|---|---:|---|---|
| email_004 | new_si_request | document_comparison | document_comparison | 0.8926 | comparison request with attachment metadata available | yes |
| email_021 | invoice_query | new_si_request | new_si_request | 0.9305 | new shipping-instruction request | yes |
| email_044 | new_si_request | document_comparison | document_comparison | 0.8926 | comparison request with attachment metadata available | yes |
| email_052 | new_si_request | document_comparison | document_comparison | 0.4566 | comparison request with attachment metadata available | yes |
| email_061 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_064 | new_si_request | document_comparison | document_comparison | 0.4566 | comparison request with attachment metadata available | yes |
| email_076 | invoice_query | general_message | general_message | 0.9465 | general operational message | yes |
| email_086 | new_si_request | general_message | general_message | 0.8498 | general operational message | yes |
| email_089 | general_message | new_si_request | new_si_request | 0.8427 | new shipping-instruction request | yes |
| email_129 | new_si_request | document_comparison | document_comparison | 0.8926 | comparison request with attachment metadata available | yes |
| email_159 | invoice_query | general_message | general_message | 0.9465 | general operational message | yes |
| email_171 | new_si_request | document_comparison | document_comparison | 0.8926 | comparison request with attachment metadata available | yes |
| email_189 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_200 | new_si_request | general_message | general_message | 0.8498 | general operational message | yes |
| email_208 | new_si_request | document_comparison | document_comparison | 0.8926 | comparison request with attachment metadata available | yes |
| email_229 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_232 | invoice_query | general_message | general_message | 0.6696 | general operational message | yes |
| email_235 | new_si_request | document_comparison | document_comparison | 0.8926 | comparison request with attachment metadata available | yes |
| email_238 | new_si_request | general_message | general_message | 0.8498 | general operational message | yes |
| email_250 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_252 | new_si_request | general_message | general_message | 0.5911 | general operational message | yes |
| email_256 | new_si_request | document_comparison | document_comparison | 0.4566 | comparison request with attachment metadata available | yes |
| email_263 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_266 | general_message | new_si_request | new_si_request | 0.8427 | new shipping-instruction request | yes |
| email_281 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_297 | invoice_query | general_message | general_message | 0.6696 | general operational message | yes |
| email_329 | spam | invoice_query | spam | 0.6863 | spam/promotional or phishing-like message | no/unclear |
| email_341 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_347 | new_si_request | general_message | general_message | 0.8168 | general operational message | yes |
| email_366 | invoice_query | general_message | general_message | 0.9465 | general operational message | yes |
| email_378 | new_si_request | document_comparison | document_comparison | 0.4566 | comparison request with attachment metadata available | yes |
| email_381 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_383 | new_si_request | document_comparison | document_comparison | 0.4566 | comparison request with attachment metadata available | yes |
| email_385 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_387 | spam | invoice_query | spam | 0.6863 | spam/promotional or phishing-like message | no/unclear |
| email_399 | invoice_query | general_message | general_message | 0.6696 | general operational message | yes |
| email_410 | new_si_request | document_comparison | document_comparison | 0.8926 | comparison request with attachment metadata available | yes |
| email_436 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_440 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_454 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_480 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_486 | new_si_request | document_comparison | document_comparison | 0.7635 | comparison workflow awaiting a requested draft BL | yes |
| email_501 | document_comparison | invoice_query | invoice_query | 0.4738 | invoice/payment enquiry | yes |
| email_504 | new_si_request | document_comparison | document_comparison | 0.5849 | comparison request with attachment metadata available | yes |
| email_512 | new_si_request | document_comparison | document_comparison | 0.7800 | comparison request with attachment metadata available | yes |

## Pattern A / Pattern B check

- Pattern A public examples: email_003, email_006, email_016, email_018, email_036, email_038, email_047, email_049, email_050, email_061, email_063, email_066, email_077, email_080, email_081, email_088, email_092, email_095, email_100, email_105, email_109, email_114, email_136, email_141, email_152, email_158, email_161, email_176, email_186, email_187, email_189, email_190, email_195, email_199, email_207, email_210, email_220, email_223, email_229, email_237, email_242, email_247, email_250, email_259, email_261, email_263, email_265, email_271, email_281, email_282, email_288, email_292, email_299, email_301, email_305, email_309, email_318, email_319, email_321, email_326, email_337, email_341, email_343, email_350, email_381, email_384, email_385, email_401, email_419, email_421, email_423, email_424, email_432, email_436, email_440, email_442, email_444, email_446, email_447, email_448, email_451, email_454, email_456, email_459, email_465, email_476, email_480, email_482, email_486, email_493, email_495.
- Pattern B public examples: email_007, email_008, email_014, email_019, email_020, email_022, email_023, email_027, email_028, email_029, email_030, email_033, email_035, email_039, email_042, email_054, email_057, email_067, email_073, email_079, email_084, email_093, email_094, email_101, email_103, email_106, email_110, email_120, email_122, email_124, email_125, email_127, email_130, email_131, email_135, email_137, email_138, email_148, email_149, email_151, email_154, email_157, email_162, email_163, email_164, email_166, email_168, email_172, email_177, email_181, email_183, email_192, email_193, email_196, email_201, email_202, email_205, email_209, email_214, email_217, email_221, email_228, email_233, email_240, email_244, email_245, email_246, email_251, email_257, email_260, email_264, email_276, email_277, email_278, email_279, email_283, email_289, email_290, email_293, email_295, email_306, email_308, email_310, email_311, email_317, email_320, email_322, email_327, email_336, email_338, email_339, email_344, email_352, email_353, email_357, email_358, email_359, email_360, email_362, email_368, email_370, email_371, email_376, email_380, email_388, email_393, email_397, email_400, email_413, email_427, email_429, email_430, email_433, email_437, email_438, email_443, email_466, email_467, email_469, email_475, email_477, email_478, email_484, email_485, email_487.
- Invariant reviewed: no attachments plus a draft-BL mention is not independently sufficient; primary requested action and body structure remain decisive.

## Generalizable Defects Found

- **Resolved in R3A-2 — zero-evidence ordinal fallback.** Original behavior: a five-way `0.20` tie selected `document_comparison` through mapping order, affecting 14 public cases.
- **Synthetic regression:** `backend/tests/test_phase1_zero_signal.py` proves neutral handling, candidate-order independence, supported spam preservation, and the bare-draft-BL negative rule.
- **General runtime fix:** all-zero evidence now uses the explicit `ZERO_SIGNAL_GENERAL` neutral policy; evidence-bearing Stage 2 ties use body score, subject score, then an explicit lexical fallback rather than insertion order.
- **Post-fix public audit:** 25 zero-signal cases remain low-confidence and resolve as {'general_message': 25}; 0 resolve as `document_comparison`.
- **Open generalizable defects counted by this audit:** NONE.
- Bucket B contains three genuine immediate-comparison requests whose referenced attachments are absent; this is an input/readiness condition, not counted as a classifier defect and is not handled in this phase.
- No classifier change was made by this audit script.

## Safety statement

The script reads only `data/bundle/` through the project source adapter. It contains no expected-answer lookup, email-ID override, filename override, fixed-backlog logic, private reference access, or classifier mutation.
