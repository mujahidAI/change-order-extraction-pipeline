# Real change orders (public records)

Downloaded from public city council / agenda portals. Used only as test inputs.

| File | Source | Why it's interesting |
|---|---|---|
| `jackson_mo_co1_ejcdc.pdf` | [City of Jackson, MO](https://mccmeetingspublic.blob.core.usgovcloudapi.net/jacksonmo-meet-b3587e2f08a24de192ee37c524d21c69/ITEM-Attachment-001-33479d678204422aa457d0459c6bcb02.pdf) | EJCDC C-941 form + 13-row line-item table (sums to $159,053.00). Date issued differs between pages (Sept 18 vs Sept 17), contractor name typo on p.3, two different schedule impacts (+61 / +166 days). |
| `ramsey_mn_co1_aia_g701.pdf` | [City of Ramsey, MN](https://public.destinyhosted.com/ramsedocs/2020/CCReg/20201124_21816/11479_RJM%20Contact%20Amendment%202.pdf) | AIA G701. Digital, but text extraction drops spaces ("CityofRamseyPublicWorks"). Empty description. Days written as "Twenty (20)". |
| `marshall_mn_co10_mixed_scanned.pdf` | [City of Marshall, MN](https://mccmeetingspublic.blob.core.usgovcloudapi.net/marshall-meet-94541c331a6041098d3fed6d88be765b/ITEM-Attachment-001-9b8f38f2116c45528c027dceb815527f.pdf) | AIA G701 + backup. Pages 5-6 are a real scan (no text layer, handwritten signature/date). Contains nested sub-change-orders (sub CO #6 says +10 days; the main CO says 0). Odd number format "5030200.0000". |
| `lawrence_co8_decrease.pdf` | [City of Lawrence](https://cityoflawrence.org/sites/default/files/attachments/JG%20Case%20-%20Change%20Order%20No.%208%20-%20Water%20System%20Improvements%20-%20Phase%20II%20Contract%20B.pdf) | EJCDC. A *decrease*, printed as a positive "$14,000.00" under a "Decrease" label (sign trap). Times "NA". |
| `baxter_mn_co4_council_memo.pdf` | [City of Baxter, MN](https://mccmeetingspublic.blob.core.usgovcloudapi.net/baxtermn-meet-1ca6216d6f0d46168fa559fe8e520ff2/ITEM-Attachment-004-4561c5ad6b774dbda88e0e9dda376304.pdf) | Not a form: a narrative council memo. Two lump-sum items embedded in prose, contract price before/after. |
| `manor_tx_co1_time_only.pdf` | [City of Manor, TX](https://mccmeetingspublic.blob.core.usgovcloudapi.net/manortx-meet-6e03f53b7b1246dfa7bf22d03dde54f5/ITEM-Attachment-001-1207cc0a8545406f90090f699e182711.pdf) | Agenda summary: time extension only (+123 calendar days), no cost change, no CO date. |
