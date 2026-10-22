
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path("force-app/main/default/objects")
NS = "http://soap.sforce.com/2006/04/metadata"
ET.register_namespace("", NS)


def tag(name):
    return f"{{{NS}}}{name}"


def add(parent, name, value):
    child = ET.SubElement(parent, tag(name))
    child.text = str(value)
    return child


def save_xml(root, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="    ")
    ET.ElementTree(root).write(
        path, encoding="UTF-8", xml_declaration=True
    )


def make_object(api, label, plural, prefix, description):
    path = ROOT / api / f"{api}.object-meta.xml"
    if path.exists():
        print(f"Preserving existing object definition: {api}")
        return

    root = ET.Element(tag("CustomObject"))
    add(root, "deploymentStatus", "Deployed")
    add(root, "description", description)
    add(root, "enableActivities", "true")
    add(root, "enableBulkApi", "true")
    add(root, "enableFeeds", "true")
    add(root, "enableHistory", "true")
    add(root, "enableReports", "true")
    add(root, "enableSearch", "true")
    add(root, "label", label)

    name_field = ET.SubElement(root, tag("nameField"))
    add(name_field, "displayFormat", f"{prefix}-{{00000}}")
    add(name_field, "label", f"{label} Number")
    add(name_field, "type", "AutoNumber")

    add(root, "pluralLabel", plural)
    if api != "Payment__c":
        add(root, "sharingModel", "ReadWrite")
    save_xml(root, path)
    print(f"Created object definition: {api}")


def make_field(obj, api, label, kind, **opts):
    path = ROOT / obj / "fields" / f"{api}.field-meta.xml"
    root = ET.Element(tag("CustomField"))
    add(root, "fullName", api)

    actual_type = opts.get("returnType", "Currency") if kind == "Formula" else kind

    if kind == "Formula":
        add(root, "formula", opts["formula"])
        add(root, "formulaTreatBlanksAs", "BlankAsZero")

    add(root, "label", label)

    if kind == "Summary":
        filt = ET.SubElement(root, tag("summaryFilterItems"))
        add(filt, "field", "Payment__c.Payment_Status__c")
        add(filt, "operation", "equals")
        add(filt, "value", "Completed")
        add(root, "summaryForeignKey", "Payment__c.Invoice__c")
        add(root, "summaryOperation", "sum")
        add(root, "summarizedField", "Payment__c.Payment_Amount__c")


    if "length" in opts:
        add(root, "length", opts["length"])
    if "precision" in opts:
        add(root, "precision", opts["precision"])
    if "scale" in opts:
        add(root, "scale", opts["scale"])
    if "visibleLines" in opts:
        add(root, "visibleLines", opts["visibleLines"])
    if opts.get("unique"):
        add(root, "unique", "true")
        add(root, "caseSensitive", "false")

    if kind in ("Lookup", "MasterDetail"):
        if kind == "Lookup":
            add(root, "deleteConstraint", "SetNull")
        add(root, "referenceTo", opts["referenceTo"])
        add(root, "relationshipLabel", opts["relationshipLabel"])
        add(root, "relationshipName", opts["relationshipName"])
        if kind == "MasterDetail":
            add(root, "reparentableMasterDetail", "false")

    add(root, "type", actual_type)

    if kind == "Picklist":
        value_set = ET.SubElement(root, tag("valueSet"))
        add(value_set, "restricted", "true")
        definition = ET.SubElement(
            value_set, tag("valueSetDefinition")
        )
        add(definition, "sorted", "false")
        for value in opts["values"]:
            item = ET.SubElement(definition, tag("value"))
            add(item, "fullName", value)
            add(item, "default", "false")
            add(item, "label", value)

    save_xml(root, path)
    print(f"Created field: {obj}.{api}")


def text(obj, api, label, length=100, unique=False):
    make_field(obj, api, label, "Text",
               length=length, unique=unique)


def currency(obj, api, label):
    make_field(obj, api, label, "Currency",
               precision=16, scale=2)


def picklist(obj, api, label, values):
    make_field(obj, api, label, "Picklist", values=values)


def long_text(obj, api, label):
    make_field(obj, api, label, "LongTextArea",
               length=32768, visibleLines=5)


# Keep the project configuration aligned with the connected org.
project_file = Path("sfdx-project.json")
project = json.loads(project_file.read_text())
project["sourceApiVersion"] = "68.0"
project_file.write_text(json.dumps(project, indent=2) + "\n")

# ------------------------------------------------------------
# 1. Financial Account (the object definition already exists)
# ------------------------------------------------------------
A = "FinancialAccount__c"

picklist(A, "Account_Type__c", "Account Type",
         ["Business", "Individual"])
text(A, "Company_Name__c", "Company Name", 150)
make_field(A, "Email__c", "Email", "Email")
make_field(A, "Phone__c", "Phone", "Phone")
text(A, "Tax_ID__c", "Tax ID", 50)
currency(A, "Credit_Limit__c", "Credit Limit")
picklist(A, "Payment_Terms__c", "Payment Terms",
         ["Due on Receipt", "Net 15", "Net 30", "Net 45", "Net 60"])
picklist(A, "Account_Status__c", "Account Status",
         ["Active", "On Hold", "Closed"])
text(A, "Billing_Country__c", "Billing Country", 80)
long_text(A, "Notes__c", "Notes")

# ------------------------------------------------------------
# 2. Invoice
# ------------------------------------------------------------
I = "Invoice__c"
make_object(
    I, "Invoice", "Invoices", "INV",
    "Tracks customer invoices, due dates, amounts, and balances."
)

make_field(
    I, "FinancialAccount__c", "Financial Account", "Lookup",
    referenceTo=A,
    relationshipLabel="Invoices",
    relationshipName="Invoices"
)
make_field(I, "Invoice_Date__c", "Invoice Date", "Date")
make_field(I, "Due_Date__c", "Due Date", "Date")
picklist(I, "Invoice_Status__c", "Invoice Status",
         ["Draft", "Sent", "Partially Paid", "Paid", "Overdue", "Void"])
currency(I, "Subtotal__c", "Subtotal")
currency(I, "Tax_Amount__c", "Tax Amount")

make_field(
    I, "Total_Amount__c", "Total Amount", "Formula",
    formula="Subtotal__c + Tax_Amount__c",
    precision=16, scale=2
)

# Sum only completed payments from related Payment records.
make_field(I, "Total_Paid__c", "Total Paid", "Summary")

make_field(
    I, "Outstanding_Balance__c", "Outstanding Balance", "Formula",
    formula="Total_Amount__c - Total_Paid__c",
    precision=16, scale=2
)

make_field(
    I, "Days_Overdue__c", "Days Overdue", "Formula",
    formula=(
        'IF(AND(Outstanding_Balance__c > 0, '
        'Due_Date__c < TODAY(), NOT(ISPICKVAL(Invoice_Status__c, "Void"))), '
        'TODAY() - Due_Date__c, 0)'
    ),
    precision=3, scale=0, returnType="Number"
)
text(I, "External_Reference__c", "External Reference", 100)
long_text(I, "Invoice_Description__c", "Invoice Description")

# ------------------------------------------------------------
# 3. Payment
# ------------------------------------------------------------
P = "Payment__c"
make_object(
    P, "Payment", "Payments", "PAY",
    "Tracks payments applied to invoices."
)

# Master-detail enables native roll-up summaries on Invoice.
make_field(
    P, "Invoice__c", "Invoice", "MasterDetail",
    referenceTo=I,
    relationshipLabel="Payments",
    relationshipName="Payments"
)
make_field(P, "Payment_Date__c", "Payment Date", "Date")
currency(P, "Payment_Amount__c", "Payment Amount")
picklist(P, "Payment_Method__c", "Payment Method",
         ["Bank Transfer", "Cash", "Card", "Cheque", "Other"])
picklist(P, "Payment_Status__c", "Payment Status",
         ["Pending", "Completed", "Failed", "Refunded"])
text(P, "Transaction_Reference__c", "Transaction Reference", 100)
text(P, "Currency_Code__c", "Currency Code", 3)
long_text(P, "Payment_Notes__c", "Payment Notes")

print("\nMetadata generation complete.")
print("Review the generated files before deploying.")
