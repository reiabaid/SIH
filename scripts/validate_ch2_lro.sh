#!/usr/bin/env bash
# ==============================================================================
# CH-2 x LRO Validation Checklist & Execution Script
# ==============================================================================
# The Chandrayaan-2 (CH-2) dataset is currently NOT present in the repository.
# To run this script, you must first obtain real CH-2 PDS4 data and place it 
# in the correct directories as instructed below.
# ==============================================================================

set -e

echo "Starting CH-2 x LRO Validation Requirements Check..."

# 1. Check for CH-2 inventory CSV
if [ ! -f "data/ch2_inventory.csv" ]; then
    echo "[BLOCKER] data/ch2_inventory.csv is missing!"
    echo "Please download the CH-2 TMC/OHRC inventory and place it in the data directory."
    echo "It should contain the same columns as lro_inventory.csv."
    exit 1
fi

# 2. Check for CH-2 actual image files
CH2_FILES=$(find data/ch2_ohrc -type f -name "*.xml" 2>/dev/null | wc -l)
if [ "$CH2_FILES" -eq 0 ]; then
    echo "[BLOCKER] No CH-2 PDS4 XML files found in data/ch2_ohrc/!"
    echo "Please place the actual CH-2 PDS4 imagery here before running a cross-instrument match."
    exit 1
fi

echo "[OK] All CH-2 data prerequisites met."
echo "Proceeding with cross-instrument validation run..."

# Replace the IDs below with actual IDs from the inventory once available.
PRODUCT_A="TBD_LRO_ID" 
PRODUCT_B="TBD_CH2_ID"

if [ "$PRODUCT_A" == "TBD_LRO_ID" ]; then
    echo "[INFO] Please edit this script with the actual product IDs once the inventory is populated."
    exit 1
fi

echo "Registering cross-instrument job..."
curl -X POST http://127.0.0.1:8000/register \
  -H "Content-Type: application/json" \
  -d "{\"product_a_id\": \"$PRODUCT_A\", \"product_b_id\": \"$PRODUCT_B\", \"algorithm\": \"rung1\"}"

echo ""
echo "Please monitor the frontend or use the returned job_id to fetch artefacts."
