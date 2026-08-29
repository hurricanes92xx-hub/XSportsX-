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

/** Local-only TV pairing. Credentials stay on the user's LAN. */
class LocalPairingHost(
    private val context: Context,
    private val onConnected: () -> Unit
) {
    data class Info(val address: String, val port: Int, val code: String, val qrPayload: String)

    private val executor = Executors.newCachedThreadPool()
    private var server: ServerSocket? = null
    private var expectedCode = ""
    private var active = false
    private var currentInfo: Info? = null

    fun start(): Info? {
        if (active) return currentInfo
        val ip = localIpv4() ?: return null
        val socket = ServerSocket(0).apply { reuseAddress = true }
        server = socket
        expectedCode = UUID.randomUUID().toString().replace("-", "").take(8).uppercase()
        active = true
        currentInfo = Info(ip, socket.localPort, expectedCode, "http://$ip:${socket.localPort}/pair?code=$expectedCode")
        executor.execute { acceptLoop(socket) }
        return currentInfo
    }

    private fun acceptLoop(socket: ServerSocket) {
        while (active) {
            val client = runCatching { socket.accept() }.getOrNull() ?: break
            executor.execute { handle(client) }
        }
    }

    private fun handle(client: Socket) {
        client.use { socket ->
            runCatching {
                socket.soTimeout = 10_000
                val reader = BufferedReader(InputStreamReader(socket.getInputStream(), Charsets.UTF_8))
                val request = reader.readLine() ?: return
                val parts = request.split(' ')
                if (parts.size < 2 || parts[0] != "POST") {
                    respond(socket, 405, "{\"error\":\"POST required\"}")
                    return
                }
                val code = parts[1].substringAfter("code=", "").substringBefore('&')
                if (code != expectedCode) {
                    respond(socket, 403, "{\"error\":\"Pairing code is invalid or expired\"}")
                    return
                }

                var length = 0
                while (true) {
                    val line = reader.readLine() ?: return
                    if (line.isEmpty()) break
                    if (line.lowercase().startsWith("content-length:")) {
                        length = line.substringAfter(':').trim().toIntOrNull() ?: 0
                    }
                }
                if (length <= 0 || length > 32_000) {
                    respond(socket, 400, "{\"error\":\"Invalid request body\"}")
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
                    respond(socket, 400, "{\"error\":\"Incomplete request\"}")
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
                    respond(socket, 422, "{\"error\":\"Phone has no configured source\"}")
                    return
                }
                SourceStore(context).save(source)
                respond(socket, 200, "{\"ok\":true}")
                active = false
                runCatching { server?.close() }
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
        Collections.list(NetworkInterface.getNetworkInterfaces()).asSequence()
            .filter { it.isUp && !it.isLoopback && !it.isVirtual }
            .flatMap { Collections.list(it.inetAddresses).asSequence() }
            .filterIsInstance<Inet4Address>()
            .map { it.hostAddress }
            .firstOrNull { !it.startsWith("127.") && !it.startsWith("169.254.") }
    }.getOrNull()
}
