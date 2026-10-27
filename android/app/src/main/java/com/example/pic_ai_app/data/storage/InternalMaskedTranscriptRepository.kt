package com.example.pic_ai_app.data.storage

import android.content.Context
import com.example.pic_ai_app.data.serialization.MaskedTranscriptJsonSerializer
import com.example.pic_ai_app.domain.model.MaskedTranscript
import com.example.pic_ai_app.domain.repository.MaskedTranscriptRepository
import com.example.pic_ai_app.domain.repository.StoredMaskedTranscript
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class InternalMaskedTranscriptRepository(
    context: Context,
    private val serializer: MaskedTranscriptJsonSerializer = MaskedTranscriptJsonSerializer(),
) : MaskedTranscriptRepository {
    private val conversationsDirectory =
        File(context.filesDir, "storage${File.separator}conversations")
    private val fileLock = Any()

    override suspend fun save(transcript: MaskedTranscript): StoredMaskedTranscript =
        withContext(Dispatchers.IO) {
            require(CONVERSATION_ID_REGEX.matches(transcript.conversationId)) {
                "Invalid conversation ID"
            }

            synchronized(fileLock) {
                val conversationDirectory =
                    File(conversationsDirectory, transcript.conversationId)
                require(conversationDirectory.isDirectory) {
                    "Conversation directory does not exist"
                }

                val fileName =
                    "masked_result${transcript.utteranceId.toString().padStart(4, '0')}.json"
                val destination = File(conversationDirectory, fileName)
                check(!destination.exists()) { "Masked transcript file already exists" }

                val temporary = File(
                    conversationDirectory,
                    ".$fileName.${UUID.randomUUID()}.tmp",
                )

                try {
                    FileOutputStream(temporary).use { output ->
                        OutputStreamWriter(output, Charsets.UTF_8).use { writer ->
                            writer.write(serializer.serialize(transcript))
                            writer.flush()
                            output.fd.sync()
                        }
                    }

                    check(!destination.exists()) { "Masked transcript file already exists" }
                    check(temporary.renameTo(destination)) {
                        "Unable to finalize the masked transcript file"
                    }
                } finally {
                    if (temporary.exists()) temporary.delete()
                }

                StoredMaskedTranscript(
                    conversationId = transcript.conversationId,
                    utteranceId = transcript.utteranceId,
                    fileName = fileName,
                )
            }
        }

    private companion object {
        val CONVERSATION_ID_REGEX = Regex("^[0-9]{8}_[0-9]{4}(?:_[0-9]{2,})?$")
    }
}
