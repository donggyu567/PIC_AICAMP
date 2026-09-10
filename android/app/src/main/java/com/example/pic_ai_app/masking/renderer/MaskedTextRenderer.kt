package com.example.pic_ai_app.masking.renderer

import com.example.pic_ai_app.masking.model.MaskCandidate

interface MaskedTextRenderer {
    fun render(
        text: String,
        candidate: List<MaskCandidate>
    ): String
}