///usr/bin/env jbang "$0" "$@" ; exit $?
//JAVA 25
//DEPS net.java.dev.jna:jna:5.17.0

import com.sun.jna.Library;
import com.sun.jna.Native;
import com.sun.jna.Memory;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;

public class TimeToFirstRequest {

    private static final boolean IS_LINUX = System.getProperty("os.name").toLowerCase().contains("linux");
    private static final int CPU_SETSIZE = 1024;
    private static final int CPU_SET_BYTES = CPU_SETSIZE / 8; // 128 bytes

    public interface CLibrary extends Library {
        CLibrary INSTANCE = IS_LINUX ? Native.load("c", CLibrary.class) : null;
        int sched_setaffinity(int pid, int cpusetsize, Memory mask);
    }

    /**
     * Pin the current process to a specific CPU core (Linux only).
     * Returns 0 on success, -1 on failure or non-Linux.
     */
    static int pinToCore(int core) {
        if (!IS_LINUX) {
            return -1;
        }
        if (core < 0 || core >= CPU_SETSIZE) {
            return -1;
        }
        Memory cpuset = new Memory(CPU_SET_BYTES);
        cpuset.clear();
        // Set the bit for the target core: byte index = core/8, bit = core%8
        int byteIndex = core / 8;
        byte bit = (byte) (1 << (core % 8));
        cpuset.setByte(byteIndex, bit);
        return CLibrary.INSTANCE.sched_setaffinity(0, CPU_SET_BYTES, cpuset);
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 4) {
            System.err.printf("Usage: TimeToFirstRequest <command> <log_path> <url> <core> [timeout in seconds]%n");
            System.err.printf("Example: TimeToFirstRequest \"java -jar app.jar\" \"/tmp/my.log\" http://localhost:8080/health 4%n");
            System.exit(1);
        }

        String command = args[0];
        String logPath = args[1];
        String url = args[2];
        int core = Integer.parseInt(args[3]);
        long timeoutNs = 5_000_000_000L;

        if (args.length >= 6) {
            timeoutNs = Long.parseLong(args[5]) * 1_000_000_000L;
        }

        // Parse URL
        String host;
        int port;
        String path;
        String u = url;
        if (u.startsWith("http://")) {
            u = u.substring(7);
        } else if (u.startsWith("https://")) {
            System.err.println("HTTPS not supported");
            System.exit(1);
        }

        int slashIdx = u.indexOf('/');
        String hostPort = slashIdx >= 0 ? u.substring(0, slashIdx) : u;
        path = slashIdx >= 0 ? u.substring(slashIdx) : "/";

        int colonIdx = hostPort.indexOf(':');
        if (colonIdx >= 0) {
            host = hostPort.substring(0, colonIdx);
            port = Integer.parseInt(hostPort.substring(colonIdx + 1));
        } else {
            host = hostPort;
            port = 80;
        }

        // Parse command into arguments
        String[] cmdArgs = command.split(" ");
        if (cmdArgs.length == 0) {
            System.err.println("Empty command");
            System.exit(1);
        }

        // Build HTTP request
        byte[] req = ("GET " + path + " HTTP/1.0\r\nHost: " + host + "\r\n\r\n").getBytes(StandardCharsets.US_ASCII);

        // Prepare process
        ProcessBuilder pb = new ProcessBuilder(cmdArgs);
        if (!logPath.isEmpty() && !logPath.equals("/dev/null")) {
            pb.redirectOutput(Path.of(logPath).toFile());
            pb.redirectErrorStream(true);
        } else if (logPath.equals("/dev/null")) {
            pb.redirectOutput(ProcessBuilder.Redirect.DISCARD);
            pb.redirectErrorStream(true);
        }

        // Pin current process to the specified core (Linux only)
        if (pinToCore(core) == -1 && IS_LINUX) {
            System.err.printf("Warning: Failed to pin process to core %d%n", core);
        }

        // Start process and record time
        long startTime = System.nanoTime();
        Process process = pb.start();

        int attempts = 0;
        int code = 0;
        long endTime = 0;
        byte[] buf = new byte[64];
        InetSocketAddress addr = new InetSocketAddress(host, port);

        // Poll URL until we get 2xx response
        while ((System.nanoTime() - startTime) < timeoutNs) {
            attempts++;
            try (Socket sock = new Socket()) {
                sock.connect(addr, 1000);
                OutputStream out = sock.getOutputStream();
                out.write(req);
                out.flush();
                InputStream in = sock.getInputStream();
                int n = in.read(buf);
                if (n > 0) {
                    String response = new String(buf, 0, n, StandardCharsets.US_ASCII);
                    // Parse "HTTP/x.x CODE"
                    int spaceIdx = response.indexOf(' ');
                    if (spaceIdx >= 0) {
                        int endIdx = response.indexOf(' ', spaceIdx + 1);
                        if (endIdx < 0) endIdx = response.indexOf('\r', spaceIdx + 1);
                        if (endIdx < 0) endIdx = response.length();
                        code = Integer.parseInt(response.substring(spaceIdx + 1, endIdx));
                        if (code >= 200 && code < 300) {
                            endTime = System.nanoTime();
                            break;
                        }
                    }
                }
            } catch (IOException _) {
                // Connection refused or other error - retry
            }
        }

        if (endTime == 0) {
            endTime = System.nanoTime();
        }

        System.out.printf("http_code=%d attempts=%d elapsed=%d ns%n", code, attempts, endTime - startTime);

        // Clean up: kill child process
        process.destroyForcibly();
        process.waitFor();

        System.exit((code >= 200 && code < 300) ? 0 : 1);
    }
}
