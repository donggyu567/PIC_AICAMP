package com.example.pic_ai_app.data.remote

import com.example.pic_ai_app.data.serialization.MaskedTranscriptJsonSerializer
import com.example.pic_ai_app.domain.model.MaskedTranscript
import com.example.pic_ai_app.domain.remote.MaskedTranscriptSender
import com.example.pic_ai_app.domain.remote.MaskedTranscriptTransmissionException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.util.concurrent.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class HttpMaskedTranscriptSender(
    endpointUrl: String,
    private val serializer: MaskedTranscriptJsonSerializer = MaskedTranscriptJsonSerializer(),
) : MaskedTranscriptSender {
    private val endpoint: URL = validateEndpoint(endpointUrl)

    override suspend fun send(transcript: MaskedTranscript): Unit = withContext(Dispatchers.IO) {
        val payload = serializer.serialize(transcript).toByteArray(Charsets.UTF_8)
        var connection: HttpURLConnection? = null
        try {
            connection = endpoint.openConnection() as? HttpURLConnection
                ?: throw MaskedTranscriptTransmissionException()
            connection.requestMethod = "POST"
            connection.connectTimeout = CONNECT_TIMEOUT_MILLIS
            connection.readTimeout = READ_TIMEOUT_MILLIS
            connection.doOutput = true
            connection.useCaches = false
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            connection.setRequestProperty("Accept", "application/json")
            connection.setFixedLengthStreamingMode(payload.size)

            connection.outputStream.use { output ->
                output.write(payload)
                output.flush()
            }

            val statusCode = connection.responseCode
            if (statusCode !in 200..299) {
                connection.errorStream?.use { it.copyTo(DiscardingOutputStream) }
                throw MaskedTranscriptTransmissionException()
            }
            connection.inputStream.use { it.copyTo(DiscardingOutputStream) }
            Unit
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (failure: MaskedTranscriptTransmissionException) {
            throw failure
        } catch (_: Exception) {
            throw MaskedTranscriptTransmissionException()
        } finally {
            connection?.disconnect()
        }
    }

    private companion object {
        const val CONNECT_TIMEOUT_MILLIS = 10_000
        const val READ_TIMEOUT_MILLIS = 20_000

        val DiscardingOutputStream = object : java.io.OutputStream() {
            override fun write(value: Int) = Unit
            override fun write(buffer: ByteArray, offset: Int, length: Int) = Unit
        }

        fun validateEndpoint(value: String): URL {
            require(value.isNotBlank()) { "API endpoint must not be blank" }
            val uri = URI(value)
            require(uri.scheme == "http" || uri.scheme == "https") {
                "API endpoint must use HTTP or HTTPS"
            }
            require(!uri.host.isNullOrBlank()) { "API endpoint must include a host" }
            return uri.toURL()
        }
    }
}
