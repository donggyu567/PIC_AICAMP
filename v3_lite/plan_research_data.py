"""Pre-generation scenario allocation. No model scores are consulted."""
from .src.common import DATA,create_json

TRAIN=[('F','bank-usage-census','financial'),('F','merchant-settlement-route','financial'),('F','authenticator-possession','identity'),('F','benefit-asset-liquid','official'),('F','account-opening-history','identity'),('F','business-signing-authority','financial'),
 ('P','community-benefit-register','official'),('P','card-migration-audit','financial'),('P','passport-ticket-correction','identity'),('P','mobile-login-otp','app'),('P','rental-document-id','identity'),('P','tax-refund-password','financial'),
 ('N','installment-interest-explain','financial'),('N','scheduled-transfer-tutorial','financial'),('N','deposit-early-close-cost','financial'),('N','water-outage-emergency','official'),('N','municipal-counter-hours','official'),('N','clinic-appointment-minimum','identity'),('N','concert-ticket-name-check','identity'),('N','workshop-delivery-address','identity'),('N','accessibility-reader-install','app'),('N','photo-editor-update','app'),('N','friends-discuss-scam-script','quotation'),('N','masked-statement-sharing','quotation')]
VALIDATION=[('F','payroll-bank-switch','financial'),('F','charity-regular-donation-route','official'),('F','travel-wallet-auth-method','app'),('F','estate-asset-ownership','identity'),('F','import-business-remittance','financial'),('F','student-payment-means','identity'),
 ('P','parcel-compensation-code','identity'),('P','employment-check-rrn','official'),('P','parking-refund-card','financial'),('P','utility-transfer-id-copy','identity'),('P','mailbox-recovery-secret','app'),('P','insurance-claim-account','financial'),
 ('N','bond-coupon-payment-query','financial'),('N','merchant-reversal-explain','financial'),('N','currency-fee-comparison','financial'),('N','gas-leak-urgent-guidance','official'),('N','public-pool-renewal','official'),('N','book-club-member-contact','identity'),('N','repair-pickup-order','identity'),('N','garden-class-confirmation','identity'),('N','offline-map-install','app'),('N','certificate-viewer-upgrade','app'),('N','parent-child-report-call','quotation'),('N','invoice-mask-training','quotation'),
 ('I','fake-archive-office','official'),('M','auction-deposit-replacement','financial'),('A','animal-camera-decoder','app'),('S','contest-nondisclosure','identity'),('T','service-penalty-countdown','official'),('L','freelancer-credit-promise','financial'),('A','delivery-remote-screen','app'),('L','store-owner-guaranteed-refinance','financial')]

if __name__=='__main__':
    out=DATA/'research_synthetic_20261117_v1'
    create_json(out/'split_plan.json',dict(schema='v3-prospective-split/1',created_before_utterance_authoring=True,
        purpose='internal_experiment',human_reviewed=False,approved_for_production=False,
        train=[dict(primary=p,family_id=f,category=c) for p,f,c in TRAIN],
        validation=[dict(primary=p,family_id=f,category=c) for p,f,c in VALIDATION],
        design='Different scenario outlines across splits; same target acts but no sentence substitutions. Original v2 TRAIN/VALIDATION screened; sealed TEST never read.'))
