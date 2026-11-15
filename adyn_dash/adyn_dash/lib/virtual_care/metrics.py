"""Susan's virtual-care definitions; team-wide harmonization remains pending."""
COMPLETED_STATUS = "completed"
COMPLETED_OUTCOME = "visit complete"
VISIT_TYPES = ["15-minute video", "25-minute video", "Async", "Unknown"]
VIDEO_TYPES = VISIT_TYPES[:2]
SKU_TYPES = {
    "VC-SYNC-15CHRG": "15-minute video",
    "VC-SYNC-25CHRG": "25-minute video",
    "VC-ASYC-ADCHRG": "Async",
    "VC-ASYC-ADFREE": "Async",
}
