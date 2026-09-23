package com.example.pic_ai_app.masking.model

data class MaskingResult(
    val maskedText: String,
    val maskedTypes: List<MaskType>
) {
    val hasMaskedData: Boolean
        get() = maskedTypes.isNotEmpty()
}
