package com.xsportsx.app

import android.content.Context
import android.os.Handler
import android.os.Looper
import org.json.JSONObject
import java.io.BufferedReader
import java.io.BufferedWriter
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.Inet4Address
import java.net.NetworkInterface
import java.net.ServerSocket
import java.net.Socket
import java.util.Collections
import java.util.UUID
import java.util.concurrent.Executors

/**
 * Local-only TV pairing. The phone and TV exchange the source over the LAN,
 * so pairing does not depend on Render, Cloudflare, or any remote service.
 */
class LocalPairingHost(
    private val context: Context,
    private val onConnected: () -> Unit
) {
    data class Info(val address: String, val port: Int, val code: String, val qrPayload: String)

    private val executor = Executors.newCachedThreadPool()
    private var server: ServerSocket? = null
    private var expectedCode: String = ""
    private var active = false

    fun start(): Info? {
        if (active) return currentInfo
        val ip = localIpv4() ?: return null
        val socket = ServerSocket(0)
        socket.reuseAddress = true
        server = socket
        expectedCode = UUID.randomUUID().toString().replace("-", "").take(8).uppercase()
        active = true
        currentInfo = Info(ip, socket.localPort, expectedCode, "http://$ip:${socket.localPort}/pair?code=$expectedCode")
        executor.execute { acceptLoop(socket) }
        return currentInfo
    }

    private var currentInfo: Info? = null

    private fun acceptLoop(socket: ServerSocket) {
        while (active) {
            val client = runCatching { socket.accept() }.getOrNull() ?: break
            executor.execute { handle(client) }
        }
    }

    private fun handle(client: Socket) {
        client.use { s ->
            runCatching {
                s.soTimeout = 10_000
                val reader = BufferedReader(InputStreamReader(s.getInputStream(), Charsets.UTF_8))
                val request = reader.readLine() ?: return
                val parts = request.split(' ')
                if (parts.size < 2 || parts[0] != "POST") {
                    respond(s, 405, "{\"error\":\"POST required\"}")
                    return
                }
                val target = parts[1]
                val code = target.substringAfter("code=", "").substringBefore('&')
                if (code != expectedCode) {
                    respond(s, 403, "{\"error\":\"Pairing code is invalid or expired\"}")
                    return
                }

                var length = 0
                while (true) {
                    val line = reader.readLine() ?: return
                    if (line.isEmpty()) break
                    val lower = line.lowercase()
                    if (lower.startsWith("content-length:")) length = lower.substringAfter(':').trim().toIntOrNull() ?: 0
                }
                if (length <= 0 || length > 32_000) {
                    respond(s, 400, "{\"error\":\"Invalid request body\"}")
                    return
                }
                val body = CharArray(length)
                var read = 0
                while (read < length) {
                    val n = reader.read(body, read, length - read)
                    if (n < 0) break
                    read += n
                }
                if (read != length) {
                    respond(s, 400, "{\"error\":\"Incomplete request\"}")
                    return
                }

                val json = JSONObject(String(body))
                val source = SourceConfig(
                    type = json.optString("type", "XTREAM"),
                    server = json.optString("server", ""),
                    username = json.optString("username", ""),
                    password = json.optString("password", ""),
                    m3uUrl = json.optString("m3uUrl", "")
                )
                if (!source.isConfigured()) {
                    respond(s, 422, "{\"error\":\"Phone has no configured source\"}")
                    return
                }
                SourceStore(context).save(source)
                respond(s, 200, "{\"ok\":true}")
                active = false
                server?.close()
                Handler(Looper.getMainLooper()).post(onConnected)
            }
        }
    }

    private fun respond(socket: Socket, status: Int, body: String) {
        val text = body.toByteArray(Charsets.UTF_8)
        val writer = BufferedWriter(OutputStreamWriter(socket.getOutputStream(), Charsets.UTF_8))
        writer.write("HTTP/1.1 $status ${if (status == 200) "OK" else "ERROR"}\r\n")
        writer.write("Content-Type: application/json; charset=utf-8\r\n")
        writer.write("Content-Length: ${text.size}\r\n")
        writer.write("Connection: close\r\n\r\n")
        writer.flush()
        socket.getOutputStream().write(text)
        socket.getOutputStream().flush()
    }

    fun stop() {
        active = false
        runCatching { server?.close() }
        server = null
        currentInfo = null
    }

    private fun localIpv4(): String? = runCatching {
        val interfaces = Collections.list(NetworkInterface.getNetworkInterfaces())
        interfaces.asSequence()
            .filter { it.isUp && !it.isLoopback && !it.isVirtual }
            .flatMap { Collections.list(it.inetAddresses).asSequence() }
            .filterIsInstance<Inet4Address>()
            .map { it.hostAddress }
            .firstOrNull { !it.startsWith("127.") && !it.startsWith("169.254.") }
    }.getOrNull()
}
