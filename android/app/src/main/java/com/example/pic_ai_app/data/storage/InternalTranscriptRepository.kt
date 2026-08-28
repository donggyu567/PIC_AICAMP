package com.example.pic_ai_app.data.storage

import android.content.Context
import com.example.pic_ai_app.data.serialization.TranscriptJsonSerializer
import com.example.pic_ai_app.domain.model.UtteranceTranscript
import com.example.pic_ai_app.domain.repository.StoredTranscript
import com.example.pic_ai_app.domain.repository.TranscriptRepository
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class InternalTranscriptRepository(
    context: Context,
    private val serializer: TranscriptJsonSerializer = TranscriptJsonSerializer(),
) : TranscriptRepository {
    private val conversationsDirectory =
        File(context.filesDir, "storage${File.separator}conversations")
    private val fileLock = Any()

    override suspend fun createConversation(baseConversationId: String): String =
        withContext(Dispatchers.IO) {
            require(BASE_ID_REGEX.matches(baseConversationId)) {
                "Invalid base conversation ID"
            }

            synchronized(fileLock) {
                ensureDirectory(conversationsDirectory)

                var suffix = 1
                while (true) {
                    val candidate = if (suffix == 1) {
                        baseConversationId
                    } else {
                        "${baseConversationId}_${suffix.toString().padStart(2, '0')}"
                    }
                    val directory = File(conversationsDirectory, candidate)
                    if (directory.mkdir()) return@synchronized candidate
                    if (!directory.exists()) {
                        error("Unable to create the conversation directory")
                    }
                    suffix += 1
                }
                error("Unreachable")
            }
        }

    override suspend fun save(transcript: UtteranceTranscript): StoredTranscript =
        withContext(Dispatchers.IO) {
            require(CONVERSATION_ID_REGEX.matches(transcript.conversationId)) {
                "Invalid conversation ID"
            }
            require(transcript.utteranceId > 0) { "Utterance ID must be positive" }

            synchronized(fileLock) {
                val conversationDirectory =
                    File(conversationsDirectory, transcript.conversationId)
                require(conversationDirectory.isDirectory) {
                    "Conversation directory does not exist"
                }

                val fileName = "raw_text_${transcript.utteranceId.toString().padStart(4, '0')}.json"
                val destination = File(conversationDirectory, fileName)
                check(!destination.exists()) { "Transcript file already exists" }

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

                    check(!destination.exists()) { "Transcript file already exists" }
                    check(temporary.renameTo(destination)) {
                        "Unable to finalize the transcript file"
                    }
                } finally {
                    if (temporary.exists()) temporary.delete()
                }

                StoredTranscript(
                    conversationId = transcript.conversationId,
                    utteranceId = transcript.utteranceId,
                    fileName = fileName,
                )
            }
        }

    private fun ensureDirectory(directory: File) {
        if (!directory.isDirectory && !directory.mkdirs()) {
            error("Unable to create the internal storage directory")
        }
    }

    private companion object {
        val BASE_ID_REGEX = Regex("^[0-9]{8}_[0-9]{4}$")
        val CONVERSATION_ID_REGEX = Regex("^[0-9]{8}_[0-9]{4}(?:_[0-9]{2,})?$")
    }
}
