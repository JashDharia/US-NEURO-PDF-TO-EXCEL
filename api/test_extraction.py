import os
from extractor import process_pdfs_to_excel

# The exact same columns the frontend sends by default for IDR Extraction
columns = [
    { "name": 'Date', "logic": 'Extract the primary date of the document or determination date (MM/DD/YYYY)' },
    { "name": 'IDR Reference Number', "logic": 'Extract the IDR reference number if present' },
    { "name": 'Determination Number', "logic": 'Extract the determination number or block number if multiple exist' },
    { "name": 'IDRE Name', "logic": 'Extract the name of the Independent Dispute Resolution Entity (IDRE)' },
    { "name": 'Insurance Company Name', "logic": 'Extract the name of the insurance company. This is usually the non-initiating party.' },
    { "name": 'Prevailing Party', "logic": 'Extract the name of the party that prevailed or won.' },
    { "name": 'Item or Service Code', "logic": 'Extract the CPT or service code associated with the claim' },
    { "name": 'Claim Number', "logic": 'Extract the claim number' },
    { "name": 'Provider Offer Amount', "logic": 'Extract the dollar amount offered by the provider/initiating party' },
    { "name": 'Insurance Offer Amount', "logic": 'Extract the dollar amount offered by the insurance company. If missing, assume 0.00' },
    { "name": 'Prevailing Offer', "logic": 'Extract the final chosen prevailing dollar amount' },
    { "name": 'Xs - Initiating Party', "logic": 'Count how many checkmarks or Xs the Initiating Party (provider) received for submitting evidence' },
    { "name": 'Xs - Non-Initiating Party', "logic": 'Count how many checkmarks or Xs the Non-Initiating Party (insurer) received for submitting evidence' },
    { "name": 'Outcome', "logic": 'If IDR: Compare prevailing party against insurer name. Provider Win = provider prevailed & insurer has Xs. Win by Default = provider prevailed & insurer has 0 Xs. Loss = insurer prevailed & provider has Xs. Loss by Default = insurer prevailed & provider has 0 Xs. For non-IDR, just summarize the outcome.' }
]

test_pdf = "/Users/jashdharia/.gemini/antigravity/scratch/us_neuro_extractor/test_pdfs/2328976_1765295618501iOYf2MPeFzDISP3750267_FinalPaymentDetermination.pdf"

print(f"Testing Extract logic on: {test_pdf}")

from dotenv import load_dotenv
load_dotenv()

output_path = process_pdfs_to_excel([test_pdf], columns)
print(f"Saved to: {output_path}")

import pandas as pd
df = pd.read_excel(output_path)
print("\nExtraction Results:")
print(df.to_string())
