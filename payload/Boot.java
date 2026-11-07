package com.kmxs.export;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.Charset;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 七猫免费小说 — 章节正文导出(纯静态注入版)
 *
 * 不依赖 Xposed / Pine / 任何 native hook (x86 模拟器上 Pine 会 SIGSEGV)。
 * 由 smali 直接调用:
 *   Boot.dumpRaw(String chapterId, String content)                    <- 写正文
 *   Boot.noteMeta(String id, String bookId, String name, String sort) <- 写章节元数据
 *
 * 输出:
 *   OUT_ROOT/chapters/<chapterId>.txt    正文
 *   OUT_ROOT/_meta.csv                   chapter_id,book_id,chapter_name,sort
 */
public class Boot {

    private static final String TAG = "QMExport";

    private static final String APP_PRIVATE = "/sdcard/Android/data/com.kmxs.reader/files/";

    /**
     * 自定义导出目录配置文件。
     *   adb push loc.txt /sdcard/Android/data/com.kmxs.reader/files/QMExport/location.txt
     */
    private static final String CONFIG_FILE = APP_PRIVATE + "QMExport/location.txt";
    private static final String PUBLIC_DIR = "/sdcard/Download/QimaoBooks";
    private static final String FALLBACK_DIR = APP_PRIVATE + "QimaoBooks";

    /** id -> "id,bookId,name,sort" */
    private static final Map<String, String> metaMap =
            Collections.synchronizedMap(new LinkedHashMap<String, String>());

    static volatile String OUT_ROOT = FALLBACK_DIR;
    private static volatile boolean inited = false;

    // ---------------- 入口: 由 Application.attachBaseContext 调用 ----------------
    public static synchronized void install() {
        if (inited) return;
        inited = true;
        OUT_ROOT = pickOutRoot();
        log("导出目录: " + OUT_ROOT);
        try {
            File dir = new File(OUT_ROOT);
            dir.mkdirs();
            new File(dir, "chapters").mkdirs();
        } catch (Throwable t) {
            log("创建目录失败: " + t);
        }
    }

    // ---------------- 供 smali 调用: 写正文 ----------------
    public static void dumpRaw(final String chapterId, final String content) {
        if (chapterId == null || content == null || content.length() < 2) return;
        if (!inited) install();
        try {
            File chapDir = new File(OUT_ROOT, "chapters");
            if (!chapDir.exists()) chapDir.mkdirs();
            File f = new File(chapDir, safe(chapterId) + ".txt");
            if (f.exists()) return;          // 不重复写
            String body = cleanContent(content);
            write(f, body, false);
            log("OK " + f.getName() + " (" + body.length() + " 字)");
        } catch (Throwable t) {
            log("dumpRaw failed: " + t);
        }
    }

    // ---------------- 供 smali 调用: 记元数据 ----------------
    public static void noteMeta(String chapterId, String bookId, String chapterName, String sort) {
        if (chapterId == null) return;
        if (metaMap.containsKey(chapterId)) return;
        metaMap.put(chapterId, q(chapterId) + "," + q(bookId) + "," + q(chapterName) + "," + q(sort));
        if (metaMap.size() <= 3 || metaMap.size() % 5 == 0) flushMeta();
    }

    private static synchronized void flushMeta() {
        if (!inited) install();
        try {
            StringBuilder sb = new StringBuilder();
            sb.append("chapter_id,book_id,chapter_name,sort\n");
            for (String line : metaMap.values()) sb.append(line).append("\n");
            File f = new File(OUT_ROOT, "_meta.csv");
            write(f, sb.toString(), false);
        } catch (Throwable t) {
            log("flushMeta failed: " + t);
        }
    }

    // ---------------- 目录选择 ----------------
    private static String pickOutRoot() {
        try {
            String custom = readFirstLine(CONFIG_FILE);
            if (custom != null && canWrite(custom)) {
                log("使用自定义目录(location.txt): " + custom);
                return custom;
            }
        } catch (Throwable t) {
            log("读取 location.txt 失败: " + t);
        }
        if (canWrite("/sdcard/Download")) {
            log("使用公共下载目录: " + PUBLIC_DIR);
            return PUBLIC_DIR;
        }
        log("公共目录不可写, 回落到私有目录: " + FALLBACK_DIR);
        return FALLBACK_DIR;
    }

    private static String readFirstLine(String path) {
        try {
            File f = new File(path);
            if (!f.exists() || !f.isFile()) return null;
            BufferedReader br = new BufferedReader(
                    new InputStreamReader(new FileInputStream(f), Charset.forName("UTF-8")));
            String line;
            try {
                line = br.readLine();
            } finally {
                try { br.close(); } catch (Throwable ignored) { }
            }
            if (line == null) return null;
            line = line.trim();
            if (line.length() == 0) return null;
            return line.endsWith("/") ? line.substring(0, line.length() - 1) : line;
        } catch (Throwable t) {
            return null;
        }
    }

    private static boolean canWrite(String dir) {
        File probe = null;
        try {
            File d = new File(dir);
            if (!d.exists() && !d.mkdirs()) return false;
            probe = new File(d, ".qmexport_probe");
            FileOutputStream fos = new FileOutputStream(probe);
            fos.write(46);
            fos.close();
            return true;
        } catch (Throwable t) {
            return false;
        } finally {
            if (probe != null) try { probe.delete(); } catch (Throwable ignored) { }
        }
    }

    // ---------------- 工具 ----------------
    private static void write(File f, String text, boolean append) {
        try {
            File parent = f.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            FileOutputStream fos = new FileOutputStream(f, append);
            OutputStreamWriter osw = new OutputStreamWriter(fos, Charset.forName("UTF-8"));
            BufferedWriter bw = new BufferedWriter(osw);
            bw.write(text);
            bw.flush();
            bw.close();
        } catch (Throwable t) {
            log("write " + f + " -> " + t);
        }
    }

    private static String cleanContent(String s) {
        String r = s.replace("\r\n", "\n");
        r = r.replaceAll("(?i)<br\\s*/?>", "\n");
        r = r.replaceAll("(?i)</p>", "\n\n");
        r = r.replaceAll("<[^>]+>", "");
        r = r.replaceAll("(?i)&nbsp;", " ");
        r = r.replaceAll("(?i)&amp;", "&");
        r = r.replaceAll("(?i)&lt;", "<");
        r = r.replaceAll("(?i)&gt;", ">");
        r = r.replaceAll("(?i)&quot;", "\"");
        r = r.replaceAll("\n{3,}", "\n\n");
        return r.trim();
    }

    private static String safe(String s) {
        if (s == null) return "unknown";
        return s.replaceAll("[^A-Za-z0-9_\\-]", "_");
    }

    private static String q(String s) {
        if (s == null) return "";
        return s.contains(",") ? ("\"" + s.replace("\"", "'") + "\"") : s;
    }

    private static void log(String m) {
        System.out.println(TAG + ": " + m);
    }
}
