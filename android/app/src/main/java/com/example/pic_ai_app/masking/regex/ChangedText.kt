package com.example.pic_ai_app.masking.regex

internal data class ChangedText(
    val text: String,
    val originalOffsets: List<Int>,
) {
    init {
        require(originalOffsets.size == text.length + 1) {
            "Every changed-text boundary must have an original offset"
        }
    }

    companion object {
        fun from(text: String): ChangedText = ChangedText(
            text = text,
            originalOffsets = (0..text.length).toList(),
        )
    }
}

internal fun ChangedText.replaceMatches(
    regex: Regex,
    replacement: (MatchResult) -> String,
): ChangedText {
    val changed = StringBuilder(text.length)
    val changedOffsets = mutableListOf(originalOffsets.first())
    var cursor = 0

    for (match in regex.findAll(text)) {
        val matchStart = match.range.first
        val matchEndExclusive = match.range.last + 1

        while (cursor < matchStart) {
            changed.append(text[cursor])
            cursor += 1
            changedOffsets.add(originalOffsets[cursor])
        }

        val replacementText = replacement(match)
        changed.append(replacementText)

        val consumedLength = matchEndExclusive - matchStart
        replacementText.indices.forEach { index ->
            val changedBoundary = index + 1
            val consumedBoundary =
                (changedBoundary * consumedLength + replacementText.length - 1) /
                    replacementText.length

            changedOffsets.add(
                originalOffsets[matchStart + consumedBoundary],
            )
        }

        cursor = matchEndExclusive
    }

    while (cursor < text.length) {
        changed.append(text[cursor])
        cursor += 1
        changedOffsets.add(originalOffsets[cursor])
    }

    return ChangedText(
        text = changed.toString(),
        originalOffsets = changedOffsets,
    )
}
