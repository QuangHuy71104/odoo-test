# KMS Team 02 Week 12 - Access Control Matrix

**Business:** Triple H & T Co., Ltd. — IT Hardware and Software Service
**Pipeline:** Odoo Knowledge → XML-RPC → Chunking → Metadata Tagging → ChromaDB/RAG
**Prepared by:** KMS Team 02 | Week 12 Submission

---

## Required Metadata Schema

```json
{
  "page_content": "Cleaned SOP content extracted from Odoo Knowledge...",
  "metadata": {
    "title": "PO1: SSD, RAM & HDD Replenishment and Backorder SOP",
    "workspace_dimension": "purchase",
    "access_role": "it_staff",
    "tags": "SOP, Purchase, Inventory, Replenishment"
  }
}
```

---

## Access Control Matrix

| Code | Article Title | Workspace Dimension | Access Role | Tags | Target Synonym List |
|------|--------------|--------------------|-----------|----|---|
| SO1 | SO1: CPU/GPU Stock Reservation Check before Sales Order Confirmation | `sales` | `it_staff` | SOP, Hardware, Inventory, SalesOrder, CPU, GPU | stock reservation; reserve stock; cannot deliver; GPU shortage; CPU availability; forecasted quantity |
| SO2 | SO2: RAM, SSD, and HDD Sales Delivery Backorder Procedure | `sales` | `it_staff` | SOP, Inventory, SalesOrder, Delivery, RAM, SSD, HDD | backorder; partial delivery; RAM shortage; SSD stock; HDD delayed; reserved quantity |
| SO3 | SO3: High-Value Product Pricing Verification before Quotation Approval | `sales` | `public` | SOP, Pricing, Quotation, CustomerSupport | wrong price; price mismatch; quotation total; outdated price list; discount; margin |
| SO4 | SO4: Sales Tax Verification for Hardware and Network Products | `sales` | `public` | SOP, Tax, Invoice, SalesOrder | VAT; tax; wrong tax; fiscal position; invoice total; tax-inclusive; tax-exclusive |
| PO1 | PO1: SSD, RAM & HDD Replenishment and Backorder SOP | `purchase` | `it_staff` | SOP, Purchase, Inventory, Replenishment, SSD, RAM, HDD | replenishment; reorder; storage purchase; SSD purchase; HDD purchase; reorder quantity |
| PO2 | PO2: Purchase Order Vendor Mapping and RFQ Validation SOP | `purchase` | `it_staff` | SOP, Purchase, VendorMapping, RFQ, PO | vendor mapping; supplier mapping; RFQ; vendor product code; wrong supplier; vendor SKU |
| TICKET1 | TICKET1: Vendor Warranty Escalation Evidence Checklist | `support` | `it_staff` | SOP, Helpdesk, Warranty, VendorEscalation | warranty; replacement; vendor escalation; serial number; purchase proof; defect evidence |
| TICKET2 | TICKET2: Repeated Support Issues to Knowledge Article Conversion SOP | `support` | `public` | SOP, Helpdesk, KnowledgeManagement | repeated ticket; recurring issue; knowledge article; troubleshooting; reopened ticket |
| TICKET3 | TICKET3: Customer Inquiry Triage SOP | `customer_service` | `public` | SOP, CustomerService, Inquiry | customer inquiry; customer question; order status; product question; customer follow-up |
| TICKET4 | TICKET4: Delivery Delay Customer Response SOP | `customer_service` | `public` | SOP, CustomerService, DeliveryDelay, Backorder | delivery delay; late delivery; order not received; backorder; revised delivery date |
| TICKET5 | TICKET5: Price and Tax Explanation for Customers SOP | `customer_service` | `public` | SOP, CustomerService, Pricing, Tax | price difference; invoice total; VAT; tax explanation; quotation mismatch; wrong price |
| TICKET6 | TICKET6: Warranty and Replacement Customer Response SOP | `customer_service` | `public` | SOP, CustomerService, Warranty, Replacement | warranty request; replacement request; defective product; broken item; return product |
| TICKET7 | TICKET7: Customer Warranty Escalation and Evidence Review SOP | `support` | `public` | SOP, Support, Warranty, Customer, Hardware | warranty escalation; replacement evidence; defective hardware; customer warranty claim; serial number proof; support evidence; vendor warranty |
| IT1 | IT1: IT Engineer Onboarding Protocol | `it` | `it_staff` | Onboarding, IT, Security | welcome new developer; onboarding developer; new engineer setup; new IT hire; orientation |
| IT2 | IT2: Network Security and System Firewall Policy | `it` | `it_staff` | NetworkSecurity, Firewall, IT | system safety; firewall policy; port isolation; security protocol; network incident |
| IT3 | IT3: Admin Access Request and Privilege Review SOP | `it` | `it_staff` | SOP, IT, Security, AccessControl, AdminAccess | admin access request; privilege review; elevated permission; system access approval; access log; least privilege; temporary admin |
| IT4 | IT4: Internal Account Deactivation and Asset Return SOP | `it` | `it_staff` | SOP, IT, Security, Offboarding, AssetReturn | account deactivation; asset return; laptop return; remove access; employee leaving; disable account; system access removal |
| HR1 | HR1: HR Payroll and Disciplinary Review Policy | `hr` | `hr_manager` | HR, Confidential, Disciplinary | disciplinary action; salary policy; payroll review; performance warning; HR complaint |
| HR2 | HR2: Employee Offboarding and Knowledge Retention SOP | `hr` | `hr_manager` | SOP, HR, Offboarding, KnowledgeRetention, Confidential | employee offboarding; resignation handover; role transition; knowledge transfer; exit interview; handover checklist; departing employee |
| HR3 | HR3: Confidential Recruitment Evaluation SOP | `hr` | `hr_manager` | SOP, HR, Recruitment, Confidential, Evaluation | candidate evaluation; hiring notes; interview review; recruitment decision; applicant assessment; confidential hiring; selection panel |
| GEN1 | GEN1: General Workspace Conduct Guideline | `public` | `public` | General, Conduct, Public | workspace conduct; welcome employees; general policy; acceptable behavior; company guideline |

---

## Data Cleaning and Sanitization Rules

| Rule ID | Cleaning Area | BA Standard |
|---------|--------------|-------------|
| CLEAN-01 | HTML stripping | Remove `<p>`, `<div>`, `<br>`, `<span>` and all HTML tags before vectorization |
| CLEAN-02 | Heading normalization | Use format: `Code - Article Title` |
| CLEAN-03 | P/A/S preservation | Keep Problem, Analysis, Solution visible in SOP evidence |
| CLEAN-04 | Vendor name standardization | Use official vendor names from the vendor list |
| CLEAN-05 | Product name standardization | Use exact master-data product names |
| CLEAN-06 | Customer Service tone | Customer-facing articles must use clear, polite, non-technical language |
| CLEAN-07 | Access-role tagging | Every chunk must carry `workspace_dimension` and `access_role` |
| CLEAN-08 | Synonym list preparation | Each article must include user search terms differing from exact title words |
| CLEAN-09 | No sensitive leakage | HR articles must be `access_role=hr_manager`, never `public` or `it_staff` |
| CLEAN-10 | Chunk-friendly paragraphs | Break long SOPs into Purpose, Problem, Root Cause, Steps, Checklist sections |

---

## Synonym Map for Semantic Search Testing

| Concept | Approved Synonym List |
|---------|----------------------|
| Sales Order | SO; quotation; customer order; sales confirmation; order line |
| Purchase Order | PO; RFQ; vendor order; supplier order; purchase request |
| Helpdesk Ticket | ticket; support case; customer complaint; incident; escalation |
| Customer Service | customer inquiry; customer request; customer follow-up; order status |
| Inventory | stock; on-hand; forecasted quantity; reserved quantity; availability; backorder |
| Pricing | price list; quotation price; discount; promotion; margin; unit price |
| Tax | VAT; invoice tax; tax mapping; fiscal position; tax account |
| Compatibility | fit; platform; socket; chipset; clearance; radiator support; Thunderbolt |
| Warranty | replacement; vendor claim; service tag; serial number; proof of purchase |
| Delivery Delay | late shipment; delayed delivery; cannot receive; stuck order; revised ETA |
| Vendor Mapping | supplier mapping; vendor SKU; vendor product code; approved vendor |
| Onboarding | welcome; new developer; new engineer setup; IT hire; first-day setup; orientation |
| Security | system safety; firewall; port isolation; network incident; unauthorized access |

---

## Week 11 Vector DB Validation Test Cases

| Test ID | Type | Query | Expected Articles | Allowed Role/Filter | Acceptance Rule |
|---------|------|-------|-------------------|--------------------|----|
| TEST-A1 | Semantic Search | How do we welcome a new developer into the team? | IT1; GEN1 | it_staff/public | Should retrieve IT onboarding and general conduct articles |
| TEST-A2 | Semantic Search | Customer says VAT is missing from invoice | TICKET5; SO4 | public | Should retrieve tax explanation and tax verification SOPs |
| TEST-A3 | Semantic Search | Customer wants to know why order is late | TICKET4; PO1 | public | Should retrieve delivery delay response and replenishment SOP |
| TEST-B1 | Security Filter | System safety and disciplinary actions protocol | IT2; GEN1 | it_staff OR public | **Must not return HR1** |
| TEST-B2 | Security Filter | Payroll disciplinary salary policy | HR1 only | hr_manager | Only HR manager filter should retrieve HR policy |
| TEST-B3 | Security Filter | Vendor warranty serial number | TICKET1; TICKET6 | it_staff OR public | Customer service version public; escalation it_staff |

---

## Security Acceptance Rules

1. For `it_staff` simulation, accepted `access_role` values are `it_staff` and `public` only.
2. `HR1` must **never** appear in the results of an `it_staff` filtered search.
3. Public articles can appear for all roles.
4. Customer Service articles are `public` and must not include confidential vendor cost, payroll, or internal disciplinary details.
5. HR articles appear only when `access_role` filter includes `hr_manager`.
6. Every generated chunk must carry `workspace_dimension` and `access_role` metadata.
