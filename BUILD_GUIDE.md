Financial Diagnostics App:  Build Guide
Step by step: from a clean Ubuntu machine to a Salesforce DX project deployed to a Developer Edition org and saved on GitHub.
Read this first: three gaps in the plan
Fix these before generating any metadata, or you will rebuild later.
1. DPO cannot be calculated with the current model. DPO needs payables (bills, vendors, cost of goods). The plan only has Invoice and Payment, which are receivables. Scope version 1 to DSO and cash collection; add a Bill__c object later if you want DPO.
2. Roll-ups need master-detail, not lookup. DSO needs totals per period. Roll-up Summary fields only work on master-detail relationships, so make Invoice__c → Financial_Period__c and Payment__c → Invoice__c master-detail. Keep Invoice__c → Account as a lookup.
3. Skip Period_Name__c. Every object already has a Name field; use that.
DSO formula (period level): DSO = (Total Outstanding Receivables / Total Invoiced in Period) × Days in Period
Step 1: Update Ubuntu and install base tools
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential unzip
Step 2: Install Node.js and the Salesforce CLI
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node --version

sudo npm install --global @salesforce/cli
sf --version
Optional: install VS Code (sudo snap install code --classic) and its Salesforce Extension Pack.
Step 3: Set up Git and GitHub access
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
Easiest route is the GitHub CLI:
sudo apt install -y gh
gh auth login
Choose GitHub.com, SSH, generate a new key when asked, and log in through the browser. Check it worked with gh auth status.
Step 4: Create a Developer Edition org and log in
1. Sign up at developer.salesforce.com/signup (free).
2. Verify the email and set a password.
3. Authorize the CLI:
sf org login web --alias FinDiagDev --set-default
sf org list
On a headless Ubuntu server, use sf org login web --alias FinDiagDev --set-default --browser firefox, or sf org login device if there is no browser.
Step 5: Generate the DX project
cd ~
sf project generate --name financial-diagnostics --template standard
cd financial-diagnostics
This gives you sfdx-project.json, .forceignore, .gitignore, manifest/package.xml and force-app/main/default/.
Step 6: Scaffold the folders and doc files
mkdir -p docs
mkdir -p force-app/main/default/{objects,layouts,flows,reports,dashboards,permissionsets,tabs,applications}
mkdir -p force-app/main/default/objects/{Financial_Period__c,Invoice__c,Payment__c}/fields
mkdir -p force-app/main/default/objects/Invoice__c/validationRules

touch README.md PROJECT_PLAN.md DATA_MODEL.md DEPLOYMENT.md
touch docs/BUSINESS_REQUIREMENTS.md docs/METRICS_DEFINITIONS.md docs/SAMPLE_DATA.md docs/TESTING_CHECKLIST.md
Skip the Apex folder for now; the plan is declarative first.
Step 7: Create the GitHub repo and push the skeleton
git init
git add .
git commit -m "Initial SFDX project skeleton"
gh repo create financial-diagnostics --private --source=. --remote=origin --push
Use --public if this is a portfolio piece. Never commit credentials; the CLI stores auth outside the repo, so you are safe by default.
Step 8: Write the data model
Create each file below. Folder names must match the object API name exactly.
objects/Financial_Period__c/Financial_Period__c.object-meta.xml
<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>Financial Period</label>
    <pluralLabel>Financial Periods</pluralLabel>
    <nameField>
        <label>Period Name</label>
        <type>Text</type>
    </nameField>
    <deploymentStatus>Deployed</deploymentStatus>
    <sharingModel>ReadWrite</sharingModel>
</CustomObject>
.../Financial_Period__c/fields/Start_Date__c.field-meta.xml (repeat for End_Date__c)
<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>Start_Date__c</fullName>
    <label>Start Date</label>
    <required>true</required>
    <type>Date</type>
</CustomField>
.../Invoice__c/Invoice__c.object-meta.xml
<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>Invoice</label>
    <pluralLabel>Invoices</pluralLabel>
    <nameField>
        <label>Invoice Number</label>
        <type>AutoNumber</type>
        <displayFormat>INV-{0000}</displayFormat>
        <startingNumber>1</startingNumber>
    </nameField>
    <deploymentStatus>Deployed</deploymentStatus>
    <sharingModel>ControlledByParent</sharingModel>
</CustomObject>
.../Invoice__c/fields/Financial_Period__c.field-meta.xml (master-detail)
<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>Financial_Period__c</fullName>
    <label>Financial Period</label>
    <referenceTo>Financial_Period__c</referenceTo>
    <relationshipLabel>Invoices</relationshipLabel>
    <relationshipName>Invoices</relationshipName>
    <relationshipOrder>0</relationshipOrder>
    <reparentableMasterDetail>false</reparentableMasterDetail>
    <type>MasterDetail</type>
    <writeRequiresMasterRead>false</writeRequiresMasterRead>
</CustomField>
.../Invoice__c/fields/Account__c.field-meta.xml (lookup)
<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>Account__c</fullName>
    <label>Customer</label>
    <referenceTo>Account</referenceTo>
    <relationshipLabel>Invoices</relationshipLabel>
    <relationshipName>Invoices</relationshipName>
    <type>Lookup</type>
    <deleteConstraint>Restrict</deleteConstraint>
</CustomField>
The remaining fields follow the same pattern. Define them in DATA_MODEL.md first:
Object
Field
Type
Invoice
Amount__c
Currency(16,2), required
Invoice
Due_Date__c
Date, required
Invoice
Invoice_Date__c
Date, required
Invoice
Status__c
Picklist: Open, Partially Paid, Paid, Overdue
Invoice
Amount_Paid__c
Roll-up Summary: SUM of Payment Amount
Invoice
Outstanding_Balance__c
Formula: Amount__c - Amount_Paid__c
Payment
Amount__c
Currency(16,2), required
Payment
Payment_Date__c
Date, required
Payment
Invoice__c
Master-Detail to Invoice
Period
Total_Invoiced__c
Roll-up Summary: SUM of Invoice Amount
Period
Total_Outstanding__c
Roll-up Summary: SUM of Invoice Outstanding Balance (if Salesforce blocks rolling up a formula that depends on another roll-up, calculate this in a Flow instead)
Period
Days_In_Period__c
Formula: End_Date__c - Start_Date__c + 1
Period
DSO__c
Formula: IF(Total_Invoiced__c = 0, 0, Total_Outstanding__c / Total_Invoiced__c * Days_In_Period__c)
Tip: faster than hand-writing XML is to build a field in the org UI, then pull it down with sf project retrieve start (Step 10) and commit the generated file.
Step 9: Deploy to the org
Dry run first; it catches XML mistakes without changing the org:
sf project deploy start --source-dir force-app --dry-run
sf project deploy start --source-dir force-app
sf org open
Deploy order matters when objects reference each other. If a deploy fails on a missing relationship, deploy Financial_Period__c first, then Invoice__c, then Payment__c:
sf project deploy start --source-dir force-app/main/default/objects/Financial_Period__c
sf project deploy start --source-dir force-app/main/default/objects/Invoice__c
sf project deploy start --source-dir force-app/main/default/objects/Payment__c
Step 10: Build the rest, then pull changes back
Do these in the order below. Items that are quicker in Setup can be built there and retrieved.
1. Permission set Financial_Diagnostics_User with access to all three objects and fields.
2. Tabs and app Financial_Diagnostics; assign the permission set to yourself.
3. Layouts: add the Invoices and Payments related lists.
4. Validation rule: Amount_Must_Be_Positive on Invoice (Amount__c <= 0).
5. Flows:
    ◦ Flag_Overdue_Invoices: scheduled daily; sets Status to Overdue where Due Date is past and Outstanding Balance is above zero.
    ◦ Update_Payment_Status: record-triggered on Payment; sets Partially Paid or Paid.
    ◦ Calculate_Period_Metrics: only if the roll-up and formula approach falls short.
6. Reports and dashboard: DSO by Period, Overdue Invoices by Customer, Outstanding Balance by Customer; then the Liquidity Dashboard.
7. Sample data: load 20 to 30 invoices with mixed payment timing so the DSO numbers mean something.
After building anything in the UI, retrieve it into the repo. Add the components to manifest/package.xml, or retrieve by type:
sf project retrieve start --metadata "Flow" "Report" "Dashboard" "Layout" "PermissionSet" "CustomApplication" "CustomTab"
Reports and dashboards also need their folder retrieved (for example Report:Financial_Diagnostics), or the retrieve returns nothing.
Step 11: Commit and push regularly
Use small commits tied to one piece of work:
git status
git add -A
git commit -m "Add Invoice and Payment objects with roll-ups"
git push
For each feature, work on a branch and open a PR so the history reads cleanly:
git checkout -b feature/overdue-flow
# work, then:
git push -u origin feature/overdue-flow
gh pr create --fill
gh pr merge --squash --delete-branch
git checkout main && git pull
Step 12: Write the docs
The repo is only useful as a portfolio or handover if the docs are real. Fill these in as you build, not at the end:
• README.md: the business problem (cash tied up in receivables), screenshots of the dashboard, setup and deploy in five commands, the DSO definition.
• DEPLOYMENT.md: the exact commands from Steps 2 to 9, plus the deploy order note.
• docs/METRICS_DEFINITIONS.md: the DSO formula, what counts as overdue, and why DPO is out of scope for v1.
• docs/SAMPLE_DATA.md: how you loaded the test records (sf data import tree or Data Import Wizard).
• docs/TESTING_CHECKLIST.md: a few cases with expected DSO values you calculated by hand.
Troubleshooting
Problem
Fix
sf: command not found
Close and reopen the terminal, or check npm config get prefix is on your PATH
EACCES on npm install
Use sudo npm install --global, or set an npm prefix in your home folder
Deploy says relationship target not found
Deploy objects in order (Step 9)
Cannot create roll-up
The relationship is a lookup; change it to master-detail
Session expired
sf org login web --alias FinDiagDev again
Retrieve returns empty for reports
Retrieve the report folder explicitly
Quick reference
sf org login web --alias FinDiagDev --set-default   # authorize
sf project deploy start --source-dir force-app      # push to org
sf project retrieve start --metadata "Flow"         # pull from org
sf org open                                         # open the org
git add -A && git commit -m "msg" && git push       # save to GitHub
