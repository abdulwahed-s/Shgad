"""User-approved fixed-copy snapshot; every edit or new key needs review."""

import hashlib

REVIEWED_ON = "2026-10-19"
REVIEWED_BY = "user"
REVIEW_SOURCE = "explicit_chat_confirmation"
APPROVED_TEXT_SHA256 = (
    "98e65cbc75df68410294ca4527e193706508fedef2e66555bded88f2806bb28a"
)
APPROVED_MESSAGES = {
    "period": "3eb1c212cb0404dd216715e0ca1cce18687cf9ade93887b28d0c994931cf01fd",
    "customer": "5c6f5182d165ce1942d9bd3860c52e82d85b693b19f141ae7a6f520feaffde9b",
    "no_figures": "5db3a8eefce08391839f432316b32630c44cd4613e09c4ad18b93b5b675bdbb6",
    "collections_expected_not_guaranteed": (
        "d1f8ce49ab2421c3a513e2d9d06de4d686a7dbe4faa872f50089bd8b7ceb37a7"
    ),
    "forecast": "7fec979de8af93c587a26e0612cce1ddbe956ecbec013ef7305bba16c020a0bc",
    "base": "b0010a7718c64532b014f9f2649f53e71f84a7c979f704770f9f7e45f284bfbe",
    "conservative": "cfad6c2f6be3e38a6f92d94c93591c54952d9d292d642b9ab324a9bad5f7d665",
    "stress": "c89f3895a355014a42729662a6ff92423e5ff439d58b70c841e0960df80ea4a0",
    "margin_excludes_unrecorded_costs": (
        "bd7d017b5928db8d3d814813a779460419f2510524147fda048c6ade6cf5ebf5"
    ),
    "unexplained_difference_excluded": (
        "fd40708e3b463e4eb3beae3588441b77e9554c896b975dfdb4753ce8225fed72"
    ),
    "coverage": "5f7a3fa3280cec8e84dd451a3300707e7386d6ddc956f77483c1f6ab32e86e27",
    "difference_note": (
        "15d36e36bd36066a2b43d16c85b3a72de24d561515fbc9c4460c5c8feb750eb6"
    ),
    "recorded_cash_sales": (
        "03ccf1b7b27a1f204f0c3acfc9857eae12a1c15838e450131ab07c567d0f5499"
    ),
    "credit_sales": "dbc5326fe9f3f1dabd66555279f7661c2b636d778ed94aaf1d237fbe3d34fdc9",
    "total_recorded_sales": (
        "72b8596340e2c7030c8ff391f63e690aa48d8be427201de043c4ecc09319369e"
    ),
    "unexplained_cash_difference": (
        "54e137e3b388c5beae4d48bd4e0bbcba8982a0d5a995e68688965ec469be598d"
    ),
    "cash_on_hand": "9bab37e2563c94bae6c41f596d83ad7586d03a94623c1ea737742312c8e2ea0a",
    "supplier_due": "a7382388fec47fbe03f37a4cdaa400d6da5a2ea371afeb05979afaca93d7fc1f",
    "supplier_dues": "2011bcf6c3dd5144715b158cb83399e9dbb4141dec40ca3cf8291d90f5ad376d",
    "expected_collection": (
        "d9c00790eacbb17c41744495effd0c734c85f5a9dd699688758c3f3079a02525"
    ),
    "expected_collections": (
        "d9c00790eacbb17c41744495effd0c734c85f5a9dd699688758c3f3079a02525"
    ),
    "shortfall_with_collection": (
        "4eb75325dbb706f9858deeaced209e88005aecd7d9ab913e173dfdb5504647e8"
    ),
    "shortfall_without_collection": (
        "750f4e18551beba771baa8cca81ea0962f20170dbc1869a53142886af04839d5"
    ),
    "position_confirmed": (
        "b1294936dcb432a50f6f39374cc6ab1b21c9ec156bce369f56cec15d51603f03"
    ),
    "position_with_expected": (
        "2768551b2e7ca50b45f711f4b7ba481eb479a0fcc50809ea3dda285c74c58a33"
    ),
    "receivables": "5c4069b7bd303809d04cc1760ad9f9b207c3ebdeb89e0a216c407123071a74e3",
    "payables": "2011bcf6c3dd5144715b158cb83399e9dbb4141dec40ca3cf8291d90f5ad376d",
    "estimated_gross_margin": (
        "803a5e74462b9d12def6e00b06a63edec14c30830292b160086df9d7b5530b47"
    ),
    "after_recorded_expenses": (
        "8966464f973bcc167e9b4ee70668d41939bb2b12e99bf603996cf52c3f132494"
    ),
    "unpriced_sales_count": (
        "2518ae8d80c597b8066d9214472deed73aaa5d2bedc29f89f04aae585e661e59"
    ),
    "reconciliation_amount": (
        "4df87f647f3f66e06d7a48848b5e420b422420be640695b6156a6dc4dca1c513"
    ),
    "forecast_lowest": (
        "0e31b1fdacf7b1ecee4c4d50025544535fb34335c75e1b141325b51317b0a178"
    ),
    "thousand": "840a81f8058f56fa66753174430d737b7b67c5dc508e579a43e99fa6d17e02e0",
    "iqd": "4804d2af3c17763e2ab3c6fc8b45314faf9b4fe060cbbcfac7d4c1c261dac9b8",
    "busy": "c734d0f7331b09496903591f31ccb33ba030865aa760dda379c7dabf983af720",
    "needs_internet": (
        "5c700b015fd33b0c71bc49ba085ba7e92c1e977d4cf0344169160831ca61fe1b"
    ),
    "provider_unconfigured": (
        "fd4eca74bef1684507b84c79af89861c4bd27f5a963ca4829e1d84d1b26ea6f6"
    ),
    "template_fallback": (
        "96268f2448515811be3b1d5236f76e9adade2fecae8539404dd8df8650681870"
    ),
    "clarify_period": (
        "68e45cb520651040a9ef520c4420bb3eab2bcd8e0f15ac8b590cee88a9d77061"
    ),
    "clarify_customer": (
        "96ef0e6970627cd3898d4c415b86857917a8d226edfc590625d25cbf9e8d1888"
    ),
    "clarify_request": (
        "66d9d373710c8b09afd7f1d196a24fe45e17162018d87b47e7f12b12f65e280f"
    ),
    "clarify_opening_balance": (
        "5421639b1ed6703e0d58b65678d06e55551d6357c6f48d41478724784b43e0e7"
    ),
    "clarify_costs": "756cc5547d0077bfcaa1f5b6545652ec4b9a09504bd375d5016781514263436f",
    "clarify_history": (
        "edddd608ef9a4fc767783a14ca41e7b69acd4b3faebfaf57eec9f7b3d0dd065a"
    ),
    "clarify_due_date": (
        "ccb285cdf12679b593a2ec093b305e0c47a2a5f44333b48a8e81548c4f81aeea"
    ),
    "clarify_counts": (
        "53e626d2383939739cc456b3b74b76a5a21a9a93ec5b721ef44950d34de5cbca"
    ),
    "unsupported_write": (
        "55d4f92270fb557726350a52d2a2532f8844d95531010c78301641dd0875bbdf"
    ),
    "unsafe_instruction": (
        "89a9f9b4c2d15ec92b08db7d833b323dc6c6bd016fb2d9fe2b846aa97af91e7e"
    ),
    "help": "31434b39f0a1ff63e9b6ecde06365fd7923f600f50d346d64fc97888234abcd8",
    "chat_error": "1ce9ce88d5bd93f552187750819a03f03c6887d68c57381fe13ac620e1d4ed95",
}


def review_status(key, text):
    fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return "APPROVED" if APPROVED_MESSAGES.get(key) == fingerprint else "PENDING_REVIEW"
