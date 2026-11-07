package com.kmxs.export;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XC_LoadPackage;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;

/**
 * 七猫免费小说 (com.kmxs.reader) — 章节正文导出
 *
 * 输出结构:
 *   OUT_ROOT/<书名>/<0001>_<章节名>.txt
 *   OUT_ROOT/<书名>/<书名>.txt          (合并稿, MERGE_ONE_FILE)
 *   OUT_ROOT/_index.json                (章节清单, WRITE_INDEX)
 *
 * 零 Android API 依赖: 不 import android.* / org.json.*,
 * 因此可以用任意 JDK + d8 直接编成 dex 塞回 APK。
 */
public class BookExportModule implements IXposedHookLoadPackage {

    private static final String TAG = "QMExport";

    // ==================== 可调参数 ====================
    /** 导出根目录 —— 想换位置只改这一行, 改完重新编译 dex */
    private static final String OUT_ROOT = "/sdcard/Download/QimaoBooks";
    private static final boolean MERGE_ONE_FILE = true;
    private static final boolean WRITE_INDEX = true;
    private static final boolean OVERWRITE = false;
    private static final int PAD_NUM = 4;
    // ==================================================

    private static final String PKG = "com.kmxs.reader";

    private static final String CLS_CHAPTER_ENTITY =
            "com.qimao.qmreader.reader.model.entity.ChapterContentEntity";
    private static final String CLS_PRELOAD_ENTITY =
            "com.qimao.qmreader.reader.model.entity.PreloadChapterContentEntity";
    private static final String CLS_KMCHAPTER =
            "com.qimao.qmreader.bookinfo.entity.KMChapter";
    private static final String CLS_KMBOOK =
            "com.qimao.qmservice.reader.entity.KMBook";

    private static final Map<String, ChapterMeta> metaMap = new ConcurrentHashMap<String, ChapterMeta>();
    private static final Map<String, String> bookMap = new ConcurrentHashMap<String, String>();
    private static final Map<String, Boolean> written = new ConcurrentHashMap<String, Boolean>();
    private static final Map<String, Boolean> merged = new ConcurrentHashMap<String, Boolean>();

    private static final ExecutorService POOL = Executors.newSingleThreadExecutor();

    /** 目标类的 ClassLoader, handleLoadPackage 时确定 */
    private ClassLoader loader;

    @Override
    public void handleLoadPackage(final XC_LoadPackage.LoadPackageParam lpparam) throws Throwable {
        if (lpparam.packageName == null || !PKG.equals(lpparam.packageName)) return;
        if (!lpparam.isFirstApplication) return;

        loader = lpparam.classLoader;
        if (loader == null) loader = BookExportModule.class.getClassLoader();

        try {
            new File(OUT_ROOT).mkdirs();
        } catch (Throwable ignored) {
        }
        XposedBridge.log(TAG + ": attach " + lpparam.packageName + " -> " + OUT_ROOT);

        hookBook();
        hookChapterMeta();
        hookContent();
        hookPreload();

        XposedBridge.log(TAG + ": hooks installed");
    }

    // ---------------- 书籍名 ----------------
    private void hookBook() {
        try {
            Class<?> cls = XposedHelpers.findClass(CLS_KMBOOK, loader);
            XposedHelpers.findAndHookMethod(cls, "getBookId", new XC_MethodHook() {
                @Override
                protected void afterHookedMethod(MethodHookParam param) throws Throwable {
                    Object idObj = param.getResult();
                    if (idObj == null) return;
                    final String id = String.valueOf(idObj);
                    if (bookMap.containsKey(id)) return;
                    Object nm = callSafe(param.thisObject, "getBookName");
                    if (nm == null) return;
                    String name = sanitize(String.valueOf(nm));
                    bookMap.put(id, name);
                    XposedBridge.log(TAG + ": book " + id + " -> " + name);
                }
            });
        } catch (Throwable t) {
            XposedBridge.log(TAG + ": hookBook failed " + t);
        }
    }

    // ---------------- 章节元数据 ----------------
    private void hookChapterMeta() {
        try {
            Class<?> cls = XposedHelpers.findClass(CLS_KMCHAPTER, loader);
            XposedHelpers.findAndHookMethod(cls, "getChapterId", new XC_MethodHook() {
                @Override
                protected void afterHookedMethod(MethodHookParam param) throws Throwable {
                    Object cidObj = param.getResult();
                    if (cidObj == null) return;
                    ChapterMeta m = new ChapterMeta();
                    m.bookId = str(callSafe(param.thisObject, "getBookId"));
                    m.name = str(callSafe(param.thisObject, "getChapterName"));
                    Object sortObj = callSafe(param.thisObject, "getChapterSort");
                    m.sort = (sortObj instanceof Integer) ? ((Integer) sortObj).intValue() : Integer.MAX_VALUE;
                    metaMap.put(String.valueOf(cidObj), m);
                }
            });
        } catch (Throwable t) {
            XposedBridge.log(TAG + ": hookChapterMeta failed " + t);
        }
    }

    // ---------------- 单章正文 ----------------
    private void hookContent() {
        try {
            Class<?> cls = XposedHelpers.findClass(CLS_CHAPTER_ENTITY, loader);
            XposedHelpers.findAndHookMethod(cls, "getContent", new XC_MethodHook() {
                @Override
                protected void afterHookedMethod(MethodHookParam param) throws Throwable {
                    Object c = param.getResult();
                    if (c == null) return;
                    String content = String.valueOf(c);
                    if (content.length() < 2) return;
                    String cid = str(callSafe(param.thisObject, "getId"));
                    if (cid == null) cid = str(fieldSafe(param.thisObject, "id"));
                    if (cid == null) cid = "anon_" + System.currentTimeMillis();
                    submitSave(cid, content, null);
                }
            });
            XposedBridge.log(TAG + ": hooked ChapterContentEntity");
        } catch (Throwable t) {
            XposedBridge.log(TAG + ": hookContent failed " + t);
        }
    }

    // ---------------- 预加载批量正文 ----------------
    private void hookPreload() {
        try {
            Class<?> cls = XposedHelpers.findClass(CLS_PRELOAD_ENTITY, loader);
            XposedHelpers.findAndHookMethod(cls, "getId", new XC_MethodHook() {
                @Override
                protected void afterHookedMethod(MethodHookParam param) throws Throwable {
                    Object idObj = param.getResult();
                    String id = idObj == null ? null : String.valueOf(idObj);

                    String title = str(callSafe(param.thisObject, "getTitle"));
                    if (title != null && id != null && !bookMap.containsKey(id)) {
                        bookMap.put(id, sanitize(title));
                    }

                    Object listObj = callSafe(param.thisObject, "getChapter_contents");
                    if (!(listObj instanceof List)) return;
                    List<?> list = (List<?>) listObj;
                    XposedBridge.log(TAG + ": preload batch " + list.size() + " chapters");
                    for (int i = 0; i < list.size(); i++) {
                        Object item = list.get(i);
                        if (item == null) continue;
                        String content = pickStr(item, "content");
                        String cid = pickStr(item, "id");
                        if (cid == null) cid = pickStr(item, "chapter_id");
                        if (cid == null) cid = pickStr(item, "chapterId");
                        String cname = pickStr(item, "title");
                        if (cname == null) cname = pickStr(item, "chapter_name");
                        if (cname == null) cname = pickStr(item, "chapterName");
                        if (content == null) continue;
                        if (cid != null && !metaMap.containsKey(cid)) {
                            ChapterMeta m = new ChapterMeta();
                            m.bookId = id;
                            m.name = cname;
                            m.sort = i + 1;
                            metaMap.put(cid, m);
                        }
                        submitSave(cid != null ? cid : (id + "_" + i), content, cname);
                    }
                }
            });
            XposedBridge.log(TAG + ": hooked PreloadChapterContentEntity");
        } catch (Throwable t) {
            XposedBridge.log(TAG + ": hookPreload failed " + t);
        }
    }

    // ---------------- 落盘 ----------------

    private void submitSave(final String chapterId, final String content, final String titleHint) {
        if (written.putIfAbsent(chapterId, Boolean.TRUE) != null) return;
        POOL.submit(new Runnable() {
            @Override
            public void run() {
                try {
                    saveChapter(chapterId, content, titleHint);
                } catch (Throwable t) {
                    XposedBridge.log(TAG + ": save failed " + t);
                }
                if (WRITE_INDEX) {
                    try {
                        writeIndex();
                    } catch (Throwable ignored) {
                    }
                }
            }
        });
    }

    private void saveChapter(String chapterId, String content, String titleHint) {
        ChapterMeta meta = metaMap.get(chapterId);
        String bookId = (meta != null && meta.bookId != null) ? meta.bookId : "unknown";
        String bookName = sanitize(firstNonEmpty(
                bookMap.get(bookId),
                (meta != null) ? meta.name : null,
                "book_" + bookId));
        File bookDir = new File(OUT_ROOT, bookName);
        if (!bookDir.exists() && !bookDir.mkdirs()) return;

        int sort = (meta != null) ? meta.sort : Integer.MAX_VALUE;
        String chapName = sanitize(firstNonEmpty(
                (meta != null) ? meta.name : null,
                titleHint,
                "chapter_" + chapterId));
        String num = (sort == Integer.MAX_VALUE) ? repeat('9', PAD_NUM) : pad(sort);
        File target = new File(bookDir, num + "_" + chapName + ".txt");

        if (target.exists() && !OVERWRITE) return;

        String body = cleanContent(content);
        writeFile(target, chapName + "\n\n" + body + "\n", false);
        XposedBridge.log(TAG + ": OK " + target.getAbsolutePath() + " (" + body.length() + " 字)");

        if (MERGE_ONE_FILE) {
            File mergeFile = new File(bookDir, bookName + ".txt");
            String key = bookId + "|" + target.getAbsolutePath();
            if (merged.putIfAbsent(key, Boolean.TRUE) == null) {
                writeFile(mergeFile, "\n\n\n" + chapName + "\n\n" + body + "\n", true);
                XposedBridge.log(TAG + ": MERGED -> " + mergeFile.getAbsolutePath());
            }
        }
    }

    /** 手写 JSON, 避免依赖 org.json */
    private void writeIndex() {
        try {
            File dir = new File(OUT_ROOT);
            if (!dir.exists() && !dir.mkdirs()) return;

            List<String> keys = new ArrayList<String>(metaMap.keySet());
            Collections.sort(keys, new Comparator<String>() {
                @Override
                public int compare(String a, String b) {
                    ChapterMeta ma = metaMap.get(a);
                    ChapterMeta mb = metaMap.get(b);
                    int sa = (ma != null) ? ma.sort : Integer.MAX_VALUE;
                    int sb = (mb != null) ? mb.sort : Integer.MAX_VALUE;
                    return (sa < sb) ? -1 : ((sa == sb) ? 0 : 1);
                }
            });

            StringBuilder sb = new StringBuilder();
            sb.append("[\n");
            for (int i = 0; i < keys.size(); i++) {
                String cid = keys.get(i);
                ChapterMeta m = metaMap.get(cid);
                sb.append("  {");
                sb.append("\"chapter_id\":").append(esc(cid));
                sb.append(",\"book_id\":").append(esc(m != null ? m.bookId : null));
                sb.append(",\"book_name\":").append(esc(bookMap.get(m != null ? m.bookId : null)));
                sb.append(",\"chapter_name\":").append(esc(m != null ? m.name : null));
                sb.append(",\"sort\":").append(m != null ? m.sort : -1);
                sb.append("}");
                if (i < keys.size() - 1) sb.append(",");
                sb.append("\n");
            }
            sb.append("]\n");
            writeFile(new File(OUT_ROOT, "_index.json"), sb.toString(), false);
        } catch (Throwable t) {
            XposedBridge.log(TAG + ": writeIndex failed " + t);
        }
    }

    private static void writeFile(File f, String text, boolean append) {
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
            XposedBridge.log(TAG + ": writeFile " + f + " -> " + t);
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

    // ---------------- 反射工具 ----------------

    private static Object callSafe(Object obj, String method) {
        if (obj == null) return null;
        try {
            Method m = obj.getClass().getDeclaredMethod(method);
            m.setAccessible(true);
            return m.invoke(obj);
        } catch (Throwable t) {
            return null;
        }
    }

    private static Object fieldSafe(Object obj, String name) {
        if (obj == null) return null;
        Class<?> cls = obj.getClass();
        while (cls != null) {
            try {
                Field f = cls.getDeclaredField(name);
                f.setAccessible(true);
                return f.get(obj);
            } catch (Throwable t) {
                cls = cls.getSuperclass();
            }
        }
        return null;
    }

    private static String pickStr(Object obj, String prop) {
        String getter = "get" + Character.toUpperCase(prop.charAt(0)) + prop.substring(1);
        Object v = callSafe(obj, getter);
        if (v != null) return String.valueOf(v);
        Object f = fieldSafe(obj, prop);
        return (f == null) ? null : String.valueOf(f);
    }

    private static String str(Object o) {
        return (o == null) ? null : String.valueOf(o);
    }

    private static String firstNonEmpty(String... arr) {
        if (arr == null) return null;
        for (String s : arr) {
            if (s != null && s.length() > 0) return s;
        }
        return null;
    }

    private static String sanitize(String s) {
        if (s == null || s.length() == 0) return "untitled";
        String r = s.replaceAll("[\\\\/:*?\"<>|\\r\\n\\t]", "_").replaceAll("\\s+", " ").trim();
        return (r.length() > 120) ? r.substring(0, 120) : r;
    }

    private static String esc(String s) {
        if (s == null) return "null";
        StringBuilder sb = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"') sb.append("\\\"");
            else if (c == '\\') sb.append("\\\\");
            else if (c == '\n') sb.append("\\n");
            else if (c < 0x20) sb.append(" ");
            else sb.append(c);
        }
        return sb.append("\"").toString();
    }

    private static String pad(int n) {
        return String.format(Locale.US, "%0" + PAD_NUM + "d", n);
    }

    private static String repeat(char c, int n) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < n; i++) sb.append(c);
        return sb.toString();
    }

    private static class ChapterMeta {
        String bookId;
        String name;
        int sort = Integer.MAX_VALUE;
    }
}
