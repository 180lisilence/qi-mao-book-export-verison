package com.kmxs.export;

import android.app.Activity;
import android.app.Application;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.lang.reflect.Method;
import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 七猫免费小说 - 导出插件 (静态注入版 v2)
 *
 * 不依赖 Xposed / Pine / 任何 native hook。
 * smali 调用点:
 *   Boot.install(Object app)                                          <- Application.attachBaseContext
 *   Boot.dumpRaw(String chapterId, String content)                    <- ChapterContentEntity.getContent()
 *   Boot.noteMeta(String id, String bookId, String name, String sort) <- KMChapter.getChapterName()
 *
 * v2 新增:
 *   1) 调用 App 自带 com.km.encryption.api.Security 解密 -> 导出明文
 *   2) 悬浮球 UI (可拖动), 点击弹出功能面板
 *   3) 一键导出 App 已缓存的全部章节 (KmxsReader/books) 到明文目录
 *   4) 手机端直接整理成"全集.txt"
 *   5) 设置页自动追加入口
 */
public class Boot {

    private static final String TAG = "QMExport";

    private static final String APP_PRIVATE = "/sdcard/Android/data/com.kmxs.reader/files/";
    private static final String CONFIG_FILE = APP_PRIVATE + "QMExport/location.txt";
    private static final String FLAG_DIR = APP_PRIVATE + "QMExport/";
    private static final String FLOAT_OFF = APP_PRIVATE + "QMExport/float_off";
    private static final String BALL_POS = APP_PRIVATE + "QMExport/ball_pos";
    private static final String PUBLIC_DIR = "/sdcard/Download/QimaoBooks";
    private static final String FALLBACK_DIR = APP_PRIVATE + "QimaoBooks";

    /** App 自己的章节缓存根目录候选 */
    private static final String[] CACHE_ROOTS = {
            APP_PRIVATE + "KmxsReader/books",
            "/sdcard/KmxsReader/books",
            "/sdcard/Android/data/com.kmxs.reader/files/KmxsReader/books",
    };

    private static final String FLOAT_TAG = "qm_export_ball";
    private static final String PANEL_TAG = "qm_export_panel";

    /** chapterId -> "chapterId,bookId,name,sort" */
    private static final Map<String, String> metaMap =
            Collections.synchronizedMap(new LinkedHashMap<String, String>());

    static volatile String OUT_ROOT = FALLBACK_DIR;
    private static volatile boolean inited = false;
    private static volatile Application sApp;
    private static volatile Activity sTop;
    private static Handler UI;

    // ==================================================================
    // 入口
    // ==================================================================
    public static synchronized void install(Object appOrCtx) {
        if (!inited) {
            inited = true;
            OUT_ROOT = pickOutRoot();
            try {
                File d = new File(OUT_ROOT);
                d.mkdirs();
                new File(d, "chapters").mkdirs();
                new File(d, "books").mkdirs();
                new File(d, "全集").mkdirs();
            } catch (Throwable t) {
                log("mkdirs: " + t);
            }
            log("导出目录: " + OUT_ROOT);
        }
        if (appOrCtx instanceof Application) {
            Application a = (Application) appOrCtx;
            // Sophix 会把 stub Application 换成 MainApplication,
            // 所以只要来了新的 Application 实例就在它身上再注册一次
            if (sApp != a) {
                sApp = a;
                try {
                    a.registerActivityLifecycleCallbacks(new Life());
                    log("已注册 ActivityLifecycleCallbacks -> " + a.getClass().getName());
                } catch (Throwable t) {
                    log("registerActivityLifecycleCallbacks: " + t);
                }
            }
        }
        scheduleBind();
    }

    public static void install() {
        install(null);
    }

    /**
     * Sophix 会在 attachBaseContext 之后把 stub Application 换成真正的
     * com.kmxs.reader.app.MainApplication, 之后 Activity 生命周期回调只分发给真身。
     * 这里用反射把真身找出来并在它上面注册回调。
     */
    private static void scheduleBind() {
        try {
            ui().post(new Runnable() {
                public void run() {
                    retryBind(0);
                }
            });
        } catch (Throwable t) {
            log("scheduleBind: " + t);
        }
    }

    private static void retryBind(final int n) {
        try {
            if (bindRealApp()) return;
            if (n >= 120) {
                log("绑定真实 Application 超时, 放弃");
                return;
            }
            ui().postDelayed(new Runnable() {
                public void run() {
                    retryBind(n + 1);
                }
            }, 500);
        } catch (Throwable t) {
            log("retryBind: " + t);
        }
    }

    private static boolean isStub(Application a) {
        try {
            String n = a.getClass().getName();
            return n != null && (n.indexOf("Sophix") >= 0 || n.indexOf("Stub") >= 0);
        } catch (Throwable t) {
            return false;
        }
    }

    private static boolean bindRealApp() {
        if (sApp != null && !isStub(sApp)) return true;
        Application found = null;
        try {
            Class<?> at = Class.forName("android.app.ActivityThread");
            java.lang.reflect.Method m = at.getDeclaredMethod("currentApplication");
            m.setAccessible(true);
            Object o = m.invoke(null);
            if (o instanceof Application) found = (Application) o;
        } catch (Throwable t) {
            log("currentApplication: " + t);
        }
        if (found == null) {
            try {
                Class<?> g = Class.forName("android.app.AppGlobals");
                java.lang.reflect.Method m = g.getDeclaredMethod("getInitialApplication");
                m.setAccessible(true);
                Object o = m.invoke(null);
                if (o instanceof Application) found = (Application) o;
            } catch (Throwable t) {
                log("getInitialApplication: " + t);
            }
        }
        if (found == null) {
            try {
                Class<?> at = Class.forName("android.app.ActivityThread");
                java.lang.reflect.Method m = at.getDeclaredMethod("currentActivityThread");
                m.setAccessible(true);
                Object o = m.invoke(null);
                if (o != null) {
                    java.lang.reflect.Field f = at.getDeclaredField("mInitialApplication");
                    f.setAccessible(true);
                    Object v = f.get(o);
                    if (v instanceof Application) found = (Application) v;
                }
            } catch (Throwable t) {
                log("mInitialApplication: " + t);
            }
        }
        if (found == null || found == sApp) return false;
        log("找到真实 Application: " + found.getClass().getName());
        install(found);
        return true;
    }

    private static Handler ui() {
        if (UI == null) UI = new Handler(Looper.getMainLooper());
        return UI;
    }

    private static final class Life implements Application.ActivityLifecycleCallbacks {
        public void onActivityCreated(Activity a, Bundle s) { }

        public void onActivityStarted(Activity a) { }

        public void onActivityResumed(final Activity a) {
            sTop = a;
            ui().postDelayed(new Runnable() {
                public void run() {
                    showBall(a);
                    injectSettingEntry(a);
                }
            }, 500);
        }

        public void onActivityPaused(Activity a) {
            detach(a);
        }

        public void onActivityStopped(Activity a) { }

        public void onActivitySaveInstanceState(Activity a, Bundle s) { }

        public void onActivityDestroyed(Activity a) { }
    }

    // ==================================================================
    // 悬浮球
    // ==================================================================
    private static void showBall(final Activity a) {
        if (a == null || sApp == null) return;
        try {
            if (a.isFinishing()) return;
            if (new File(FLOAT_OFF).exists()) return;
            final ViewGroup root = decor(a);
            if (root == null) return;
            if (root.findViewWithTag(FLOAT_TAG) != null) return;

            final TextView ball = new TextView(a);
            ball.setTag(FLOAT_TAG);
            ball.setText("导\n出");
            ball.setTextColor(Color.WHITE);
            ball.setTextSize(12);
            ball.setGravity(Gravity.CENTER);
            ball.setBackgroundDrawable(roundRect(0xCCFF6600, 999, 0x66FFFFFF));

            int size = dp(a, 54);
            int[] sc = screen(a);
            final int maxX = sc[0] - size;
            final int maxY = sc[1] - size - dp(a, 20);
            int[] pos = loadBallPos();

            final FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(size, size);
            lp.gravity = Gravity.TOP | Gravity.LEFT;
            lp.leftMargin = clamp(pos[0] >= 0 ? pos[0] : maxX - dp(a, 8), 0, maxX);
            lp.topMargin = clamp(pos[1] >= 0 ? pos[1] : (int) (sc[1] * 0.45), 0, maxY);
            ball.setLayoutParams(lp);

            final float[] start = new float[2];
            final int[] base = new int[2];
            final boolean[] moved = new boolean[1];

            ball.setOnTouchListener(new View.OnTouchListener() {
                public boolean onTouch(View v, MotionEvent e) {
                    FrameLayout.LayoutParams p = (FrameLayout.LayoutParams) v.getLayoutParams();
                    switch (e.getAction()) {
                        case MotionEvent.ACTION_DOWN:
                            start[0] = e.getRawX();
                            start[1] = e.getRawY();
                            base[0] = p.leftMargin;
                            base[1] = p.topMargin;
                            moved[0] = false;
                            return true;
                        case MotionEvent.ACTION_MOVE:
                            float dx = e.getRawX() - start[0];
                            float dy = e.getRawY() - start[1];
                            if (Math.abs(dx) > 6 || Math.abs(dy) > 6) moved[0] = true;
                            p.leftMargin = clamp(base[0] + (int) dx, 0, maxX);
                            p.topMargin = clamp(base[1] + (int) dy, 0, maxY);
                            v.setLayoutParams(p);
                            return true;
                        case MotionEvent.ACTION_UP:
                        case MotionEvent.ACTION_CANCEL:
                            if (!moved[0]) {
                                openPanel(a);
                            } else {
                                saveBallPos(p.leftMargin, p.topMargin);
                            }
                            return true;
                    }
                    return false;
                }
            });
            root.addView(ball);
            log("悬浮球已挂载: " + a.getClass().getName());
        } catch (Throwable t) {
            log("showBall: " + t);
        }
    }

    private static void detach(Activity a) {
        try {
            final ViewGroup root = decor(a);
            if (root == null) return;
            View v = root.findViewWithTag(FLOAT_TAG);
            if (v != null) root.removeView(v);
            View p = root.findViewWithTag(PANEL_TAG);
            if (p != null) root.removeView(p);
        } catch (Throwable t) {
            log("detach: " + t);
        }
    }

    private static ViewGroup decor(Activity a) {
        if (a == null || a.getWindow() == null) return null;
        View d = a.getWindow().getDecorView();
        return (d instanceof ViewGroup) ? (ViewGroup) d : null;
    }

    // ==================================================================
    // 功能面板
    // ==================================================================
    private static void openPanel(final Activity a) {
        try {
            final ViewGroup root = decor(a);
            if (root == null) return;
            if (root.findViewWithTag(PANEL_TAG) != null) return;

            final FrameLayout overlay = new FrameLayout(a);
            overlay.setTag(PANEL_TAG);
            overlay.setBackgroundColor(0xAA000000);
            overlay.setLayoutParams(new ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
            overlay.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    try {
                        ((ViewGroup) v.getParent()).removeView(v);
                    } catch (Throwable ignored) { }
                }
            });

            LinearLayout card = new LinearLayout(a);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setBackgroundDrawable(roundRect(0xFFF5F5F5, 18, 0x22000000));
            int pad = dp(a, 16);
            card.setPadding(pad, pad, pad, pad);
            FrameLayout.LayoutParams clp = new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            clp.gravity = Gravity.CENTER;
            clp.leftMargin = dp(a, 24);
            clp.rightMargin = dp(a, 24);
            card.setLayoutParams(clp);

            TextView title = new TextView(a);
            title.setText("七猫导出插件");
            title.setTextSize(17);
            title.setTextColor(0xFF222222);
            title.setPadding(0, 0, 0, dp(a, 6));
            card.addView(title);

            TextView sub = new TextView(a);
            sub.setText("目录: " + OUT_ROOT);
            sub.setTextSize(11);
            sub.setTextColor(0xFF777777);
            sub.setPadding(0, 0, 0, dp(a, 10));
            card.addView(sub);

            addRow(a, card, statText(), 0xFF444444, 11, null);

            addRow(a, card, "① 一键导出已缓存章节 (明文)", 0xFFE65100, 15, new Runnable() {
                public void run() {
                    doAsync("正在导出…", new Runnable() {
                        public void run() {
                            toast(exportCached());
                        }
                    });
                    removeOverlay(overlay);
                }
            });
            addRow(a, card, "② 整理成全集 txt", 0xFF1B5E20, 15, new Runnable() {
                public void run() {
                    doAsync("正在整理…", new Runnable() {
                        public void run() {
                            toast(organize());
                        }
                    });
                    removeOverlay(overlay);
                }
            });
            addRow(a, card, "③ 复制导出目录路径", 0xFF0D47A1, 15, new Runnable() {
                public void run() {
                    copy(OUT_ROOT);
                    toast("已复制: " + OUT_ROOT);
                    removeOverlay(overlay);
                }
            });
            addRow(a, card, "④ 重新选择导出目录", 0xFF37474F, 15, new Runnable() {
                public void run() {
                    OUT_ROOT = pickOutRoot();
                    flushMeta();
                    toast("目录: " + OUT_ROOT);
                    removeOverlay(overlay);
                }
            });
            addRow(a, card, "⑥ 修复密文 (重新解密已导出文件)", 0xFF00695C, 15, new Runnable() {
                public void run() {
                    doAsync("正在修复…", new Runnable() {
                        public void run() {
                            toast(redecrypt());
                        }
                    });
                    removeOverlay(overlay);
                }
            });
            final boolean off = new File(FLOAT_OFF).exists();
            addRow(a, card, off ? "⑦ 显示悬浮球" : "⑦ 隐藏悬浮球", 0xFF8E24AA, 15, new Runnable() {
                public void run() {
                    setFloatOff(!off);
                    if (!off) {
                        try {
                            ViewGroup r = decor(a);
                            View b = r == null ? null : r.findViewWithTag(FLOAT_TAG);
                            if (b != null) r.removeView(b);
                        } catch (Throwable ignored) { }
                    } else {
                        showBall(a);
                    }
                    removeOverlay(overlay);
                }
            });
            addRow(a, card, "关闭", 0xFF999999, 13, new Runnable() {
                public void run() {
                    removeOverlay(overlay);
                }
            });

            overlay.addView(card);
            root.addView(overlay);
        } catch (Throwable t) {
            log("openPanel: " + t);
        }
    }

    private static void removeOverlay(View v) {
        try {
            ViewGroup p = (ViewGroup) v.getParent();
            if (p != null) p.removeView(v);
        } catch (Throwable ignored) { }
    }

    private static void addRow(Context c, LinearLayout box, String text, int color,
                               float size, final Runnable action) {
        TextView t = new TextView(c);
        t.setText(text);
        t.setTextSize(size);
        t.setTextColor(color);
        int p = dp(c, 10);
        t.setPadding(p, p, p, p);
        if (action != null) {
            t.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    try {
                        action.run();
                    } catch (Throwable e) {
                        log("row: " + e);
                    }
                }
            });
        }
        box.addView(t);
    }

    // ==================================================================
    // 设置页追加入口
    // ==================================================================
    private static void injectSettingEntry(Activity a) {
        try {
            String cn = a.getClass().getName();
            if (cn == null || cn.indexOf("Setting") < 0) return;
            ViewGroup content = (ViewGroup) a.findViewById(android.R.id.content);
            if (content == null) return;
            LinearLayout list = findSettingList(content);
            if (list == null) return;
            if (list.findViewWithTag("qm_export_entry") != null) return;

            TextView row = new TextView(a);
            row.setTag("qm_export_entry");
            row.setText("七猫导出插件");
            row.setTextSize(15);
            row.setTextColor(0xFF222222);
            int p = dp(a, 14);
            row.setPadding(p, p, p, p);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            row.setLayoutParams(lp);
            row.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    Activity act = sTop;
                    if (act == null && v.getContext() instanceof Activity) {
                        act = (Activity) v.getContext();
                    }
                    openPanel(act);
                }
            });
            list.addView(row);
            log("已向设置页追加入口: " + cn);
        } catch (Throwable t) {
            log("injectSettingEntry: " + t);
        }
    }

    private static LinearLayout findSettingList(View v) {
        if (v instanceof ScrollView) {
            View c = ((ScrollView) v).getChildAt(0);
            if (c instanceof LinearLayout
                    && ((LinearLayout) c).getOrientation() == LinearLayout.VERTICAL
                    && ((ViewGroup) c).getChildCount() >= 2) {
                return (LinearLayout) c;
            }
        }
        if (v instanceof ViewGroup) {
            ViewGroup g = (ViewGroup) v;
            for (int i = 0; i < g.getChildCount(); i++) {
                LinearLayout r = findSettingList(g.getChildAt(i));
                if (r != null) return r;
            }
        }
        return null;
    }

    // ==================================================================
    // 一键导出 App 已缓存章节
    // ==================================================================
    public static String exportCached() {
        if (!inited) install(null);
        int books = 0, chaps = 0, skipped = 0, fail = 0;
        StringBuilder report = new StringBuilder();
        for (int i = 0; i < CACHE_ROOTS.length; i++) {
            File root = new File(CACHE_ROOTS[i]);
            File[] bd = root.listFiles();
            if (bd == null) continue;
            for (int j = 0; j < bd.length; j++) {
                File b = bd[j];
                if (!b.isDirectory()) continue;
                String bookId = b.getName();
                File[] fs = b.listFiles();
                if (fs == null || fs.length == 0) continue;
                books++;
                File outDir = new File(OUT_ROOT, "books/" + safe(bookId));
                outDir.mkdirs();
                List<File> sorted = new ArrayList<File>();
                for (int k = 0; k < fs.length; k++) {
                    if (fs[k].isFile()) sorted.add(fs[k]);
                }
                Collections.sort(sorted);
                StringBuilder all = new StringBuilder();
                for (int k = 0; k < sorted.size(); k++) {
                    File f = sorted.get(k);
                    String cid = f.getName();
                    if (cid.endsWith(".txt")) cid = cid.substring(0, cid.length() - 4);
                    else if (cid.endsWith(".epub")) cid = cid.substring(0, cid.length() - 5);
                    File out = new File(outDir, safe(cid) + ".txt");
                    if (out.exists() && out.length() > 0) {
                        skipped++;
                        continue;
                    }
                    String raw = readAll(f);
                    if (raw == null || raw.trim().length() == 0) {
                        fail++;
                        continue;
                    }
                    String plain = decrypt(raw);
                    if (plain == null || plain.trim().length() == 0) {
                        fail++;
                        continue;
                    }
                    String body = cleanContent(plain);
                    write(out, body, false);
                    all.append("\n\n").append(nameOf(cid)).append("\n\n").append(body);
                    chaps++;
                }
                if (all.length() > 0) {
                    write(new File(outDir, "_全集.txt"), all.toString().trim(), false);
                }
                report.append(bookId).append(": ").append(sorted.size()).append(" 章\n");
            }
            if (books > 0) break;
        }
        log("exportCached books=" + books + " chaps=" + chaps + " skip=" + skipped + " fail=" + fail);
        return "导出完成\n新导出 " + chaps + " 章 / " + books + " 本\n跳过 " + skipped
                + " 失败 " + fail + "\n" + report;
    }

    /** 把 chapters/ 里的正文按书合并成全集 */
    public static String organize() {
        if (!inited) install(null);
        Map<String, String> meta = loadMeta();
        Map<String, List<String>> groups = new LinkedHashMap<String, List<String>>();
        Map<String, List<String>> bodies = new LinkedHashMap<String, List<String>>();
        int total = 0;

        File chapDir = new File(OUT_ROOT, "chapters");
        File[] fs = chapDir.listFiles();
        if (fs != null) {
            for (int i = 0; i < fs.length; i++) {
                String n = fs[i].getName();
                if (!n.endsWith(".txt")) continue;
                String cid = n.substring(0, n.length() - 4);
                String bid = "unknown";
                String m = meta.get(cid);
                if (m != null) {
                    String[] a = m.split(",", -1);
                    if (a.length >= 2 && a[1].length() > 0) bid = a[1];
                }
                addChapter(groups, bodies, bid, cid, readAll(fs[i]));
                total++;
            }
        }

        File booksDir = new File(OUT_ROOT, "books");
        File[] bs = booksDir.listFiles();
        if (bs != null) {
            for (int j = 0; j < bs.length; j++) {
                if (!bs[j].isDirectory()) continue;
                File[] cf = bs[j].listFiles();
                if (cf == null) continue;
                for (int k = 0; k < cf.length; k++) {
                    String n = cf[k].getName();
                    if (!n.endsWith(".txt") || n.startsWith("_")) continue;
                    String body = readAll(cf[k]);
                    if (body == null) continue;
                    addChapter(groups, bodies, bs[j].getName(),
                            n.substring(0, n.length() - 4), body);
                    total++;
                }
            }
        }
        if (total == 0) return "没有可整理的内容, 先去看书或点 ① 导出缓存";
        File outDir = new File(OUT_ROOT, "全集");
        outDir.mkdirs();
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, List<String>> e : groups.entrySet()) {
            List<String> ids = e.getValue();
            List<String> bl = bodies.get(e.getKey());
            if (bl == null || bl.isEmpty()) continue;
            StringBuilder book = new StringBuilder();
            for (int i = 0; i < bl.size(); i++) {
                String body = bl.get(i);
                if (body == null) continue;
                String cid = i < ids.size() ? ids.get(i) : "";
                book.append("\n\n").append(nameOf(cid)).append("\n\n").append(body.trim());
            }
            if (book.length() == 0) continue;
            File f = new File(outDir, safe(e.getKey()) + "_" + bl.size() + "章.txt");
            write(f, book.toString().trim(), false);
            sb.append(e.getKey()).append(" -> ").append(f.getName()).append("\n");
        }
        return "已整理 " + groups.size() + " 本\n目录: " + outDir.getAbsolutePath() + "\n" + sb;
    }

    private static void addChapter(Map<String, List<String>> groups,
                                   Map<String, List<String>> bodies,
                                   String bookId, String chapterId, String body) {
        List<String> l = groups.get(bookId);
        List<String> b = bodies.get(bookId);
        if (l == null) {
            l = new ArrayList<String>();
            b = new ArrayList<String>();
            groups.put(bookId, l);
            bodies.put(bookId, b);
        }
        l.add(chapterId == null ? "" : chapterId);
        b.add(body == null ? "" : body);
    }

    private static String statText() {
        int c = countFiles(new File(OUT_ROOT, "chapters"));
        int b = 0;
        File bd = new File(OUT_ROOT, "books");
        File[] bs = bd.listFiles();
        if (bs != null) {
            for (int i = 0; i < bs.length; i++) {
                if (bs[i].isDirectory()) b++;
            }
        }
        int cache = countFiles(new File(CACHE_ROOTS[0]));
        return "已导出 " + c + " 章 / " + b + " 本;  App 缓存 " + cache + " 个文件";
    }

    private static int countFiles(File d) {
        try {
            File[] fs = d.listFiles();
            if (fs == null) return 0;
            int n = 0;
            for (int i = 0; i < fs.length; i++) {
                if (fs[i].isDirectory()) n += countFiles(fs[i]);
                else n++;
            }
            return n;
        } catch (Throwable t) {
            return 0;
        }
    }

    // ==================================================================
    // 解密: 直接调用 App 自带的 com.km.encryption.api.Security
    // ==================================================================
    private static String decrypt(String s) {
        if (s == null) return null;
        String t = s.trim();
        if (t.length() == 0) return s;
        if (!looksCipher(t)) return s;
        try {
            Class<?> c = Class.forName("com.km.encryption.api.Security");
            Method m = c.getDeclaredMethod("decrypt", String.class, String.class);
            m.setAccessible(true);
            Object r = m.invoke(null, null, t);
            if (r instanceof String) {
                String p = ((String) r).trim();
                if (p.length() > 0 && !p.equals("fail") && !p.equals(t)
                        && p.indexOf('\uFFFD') < 0) {
                    log("decrypt OK " + p.length() + " 字");
                    return p;
                }
            }
        } catch (Throwable e) {
            log("decrypt: " + e);
        }
        try {
            Class<?> c = Class.forName("com.km.encryption.api.Security");
            Method m = c.getDeclaredMethod("decryptV2", String.class, byte[].class);
            m.setAccessible(true);
            Object r = m.invoke(null, null, t.getBytes("UTF-8"));
            if (r instanceof byte[]) {
                byte[] b = (byte[]) r;
                if (b.length > 0) {
                    String p = strictUtf8(b);
                    if (p != null) {
                        p = p.trim();
                        if (p.length() > 0 && !p.equals("fail") && p.indexOf('\uFFFD') < 0) {
                            log("decryptV2 OK " + p.length() + " 字");
                            return p;
                        }
                    }
                    log("decryptV2 结果不是有效 UTF-8, 放弃 (" + b.length + " 字节)");
                }
            }
        } catch (Throwable e) {
            log("decryptV2: " + e);
        }
        log("解密失败, 原样写出");
        return s;
    }

    /** 严格 UTF-8 解码, 有坏字节返回 null (避免导出一堆乱码) */
    private static String strictUtf8(byte[] b) {
        try {
            java.nio.charset.CharsetDecoder dec = Charset.forName("UTF-8").newDecoder()
                    .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
                    .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT);
            return dec.decode(java.nio.ByteBuffer.wrap(b)).toString();
        } catch (Throwable t) {
            return null;
        }
    }

    /** 把 OUT_ROOT 里所有仍是密文的 .txt 重新解密 */
    public static String redecrypt() {
        if (!inited) install(null);
        int[] n = new int[]{0, 0};
        walkFix(new File(OUT_ROOT), n, 0);
        return "重新解密完成\n修复 " + n[0] + " 个, 跳过 " + n[1] + " 个";
    }

    private static void walkFix(File d, int[] n, int depth) {
        if (d == null || depth > 5) return;
        File[] fs = d.listFiles();
        if (fs == null) return;
        for (int i = 0; i < fs.length; i++) {
            File f = fs[i];
            if (f.isDirectory()) { walkFix(f, n, depth + 1); continue; }
            String nm = f.getName();
            if (!nm.endsWith(".txt") || nm.startsWith("_")) continue;
            String raw = readAll(f);
            if (raw == null) continue;
            String t = raw.trim();
            if (!looksCipher(t)) { n[1]++; continue; }
            String plain = decrypt(t);
            if (plain == null || plain.trim().length() == 0 || plain.trim().equals(t)) { n[1]++; continue; }
            write(f, cleanContent(plain), false);
            n[0]++;
        }
    }

    /** 判断是否是 base64 密文 */
    private static boolean looksCipher(String s) {
        if (s == null || s.length() < 40) return false;
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            boolean ok = (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z')
                    || (ch >= '0' && ch <= '9') || ch == '+' || ch == '/'
                    || ch == '=' || ch == '\n' || ch == '\r' || ch == ' ' || ch == '\t';
            if (!ok) return false;
        }
        return true;
    }

    // ==================================================================
    // smali 调用点
    // ==================================================================
    public static void dumpRaw(final String chapterId, final String content) {
        if (chapterId == null || content == null || content.length() < 2) return;
        if (!inited) install(null);
        try {
            File chapDir = new File(OUT_ROOT, "chapters");
            if (!chapDir.exists()) chapDir.mkdirs();
            File f = new File(chapDir, safe(chapterId) + ".txt");
            if (f.exists() && f.length() > 0) {
                String prev = readAll(f);
                if (prev == null || !looksCipher(prev.trim())) return;
                f.delete();     // 老版本留下的是密文 -> 重写
            }
            String body = cleanContent(decrypt(content));
            write(f, body, false);
            log("OK " + f.getName() + " (" + body.length() + " 字)");
        } catch (Throwable t) {
            log("dumpRaw failed: " + t);
        }
    }

    public static void noteMeta(String chapterId, String bookId, String chapterName, String sort) {
        if (chapterId == null) return;
        if (metaMap.containsKey(chapterId)) return;
        metaMap.put(chapterId, q(chapterId) + "," + q(bookId) + "," + q(chapterName) + "," + q(sort));
        if (metaMap.size() <= 3 || metaMap.size() % 5 == 0) flushMeta();
    }

    private static synchronized void flushMeta() {
        if (!inited) install(null);
        try {
            StringBuilder sb = new StringBuilder();
            sb.append("chapter_id,book_id,chapter_name,sort\n");
            for (String line : metaMap.values()) sb.append(line).append("\n");
            write(new File(OUT_ROOT, "_meta.csv"), sb.toString(), false);
        } catch (Throwable t) {
            log("flushMeta failed: " + t);
        }
    }

    private static String nameOf(String chapterId) {
        String m = metaMap.get(chapterId);
        if (m != null) {
            String[] a = m.split(",", -1);
            if (a.length >= 3 && a[2].length() > 0) return a[2];
        }
        return "章节 " + chapterId;
    }

    private static Map<String, String> loadMeta() {
        try {
            File f = new File(OUT_ROOT, "_meta.csv");
            if (!f.exists()) return metaMap;
            BufferedReader br = new BufferedReader(new InputStreamReader(
                    new FileInputStream(f), Charset.forName("UTF-8")));
            String line;
            while ((line = br.readLine()) != null) {
                String[] a = line.split(",", -1);
                if (a.length >= 2 && a[0].length() > 0 && !a[0].equals("chapter_id")) {
                    metaMap.put(a[0], line);
                }
            }
            br.close();
        } catch (Throwable t) {
            log("loadMeta: " + t);
        }
        return metaMap;
    }

    // ==================================================================
    // 目录 / 配置
    // ==================================================================
    private static String pickOutRoot() {
        try {
            String custom = readFirstLine(CONFIG_FILE);
            if (custom != null && canWrite(custom)) {
                log("使用自定义目录: " + custom);
                return custom;
            }
        } catch (Throwable t) {
            log("location.txt: " + t);
        }
        if (canWrite("/sdcard/Download")) {
            log("使用公共下载目录: " + PUBLIC_DIR);
            return PUBLIC_DIR;
        }
        log("回落到私有目录: " + FALLBACK_DIR);
        return FALLBACK_DIR;
    }

    private static void setFloatOff(boolean off) {
        try {
            new File(FLAG_DIR).mkdirs();
            File f = new File(FLOAT_OFF);
            if (off) {
                write(f, "1", false);
            } else {
                f.delete();
            }
        } catch (Throwable ignored) { }
    }

    private static void saveBallPos(int x, int y) {
        try {
            new File(FLAG_DIR).mkdirs();
            write(new File(BALL_POS), x + "," + y, false);
        } catch (Throwable ignored) { }
    }

    private static int[] loadBallPos() {
        try {
            String s = readFirstLine(BALL_POS);
            if (s == null) return new int[]{-1, -1};
            String[] a = s.split(",");
            return new int[]{Integer.parseInt(a[0].trim()), Integer.parseInt(a[1].trim())};
        } catch (Throwable t) {
            return new int[]{-1, -1};
        }
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
                try {
                    br.close();
                } catch (Throwable ignored) { }
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
            if (probe != null) {
                try {
                    probe.delete();
                } catch (Throwable ignored) { }
            }
        }
    }

    // ==================================================================
    // 工具
    // ==================================================================
    private static void doAsync(String msg, final Runnable job) {
        toast(msg);
        new Thread(new Runnable() {
            public void run() {
                try {
                    job.run();
                } catch (Throwable t) {
                    log("async: " + t);
                }
            }
        }).start();
    }

    private static void toast(final String msg) {
        try {
            ui().post(new Runnable() {
                public void run() {
                    try {
                        if (sApp == null) return;
                        Toast.makeText(sApp, msg, Toast.LENGTH_LONG).show();
                    } catch (Throwable ignored) { }
                }
            });
        } catch (Throwable ignored) { }
    }

    private static void copy(String text) {
        try {
            if (sApp == null) return;
            ClipboardManager cm =
                    (ClipboardManager) sApp.getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm != null) cm.setPrimaryClip(ClipData.newPlainText("path", text));
        } catch (Throwable t) {
            log("copy: " + t);
        }
    }

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

    private static String readAll(File f) {
        try {
            long len = f.length();
            if (len <= 0 || len > 20 * 1024 * 1024) return null;
            byte[] buf = new byte[(int) len];
            FileInputStream in = new FileInputStream(f);
            int off = 0;
            while (off < buf.length) {
                int r = in.read(buf, off, buf.length - off);
                if (r < 0) break;
                off += r;
            }
            in.close();
            return new String(buf, 0, off, "UTF-8");
        } catch (Throwable t) {
            log("readAll " + f + " -> " + t);
            return null;
        }
    }

    private static String cleanContent(String s) {
        if (s == null) return "";
        String r = s.replace("\r\n", "\n");
        r = r.replaceAll("(?i)<br\\s*/?>", "\n");
        r = r.replaceAll("(?i)</p>", "\n\n");
        r = r.replaceAll("<[^>]+>", "");
        r = r.replaceAll("(?i)&nbsp;", " ");
        r = r.replaceAll("(?i)&amp;", "&");
        r = r.replaceAll("(?i)&lt;", "<");
        r = r.replaceAll("(?i)&gt;", ">");
        r = r.replaceAll("(?i)&quot;", "\"");
        r = r.replaceAll("\u3000", "  ");
        r = r.replaceAll("\n{3,}", "\n\n");
        return r.trim();
    }

    private static String safe(String s) {
        if (s == null) return "unknown";
        return s.replaceAll("[^A-Za-z0-9_\\-\u4e00-\u9fa5]", "_");
    }

    private static String q(String s) {
        if (s == null) return "";
        return s.contains(",") ? ("\"" + s.replace("\"", "'") + "\"") : s;
    }

    private static GradientDrawable roundRect(int fill, int radiusDp, int stroke) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(fill);
        g.setCornerRadius(radiusDp);
        if (stroke != 0) g.setStroke(2, stroke);
        return g;
    }

    private static int dp(Context c, int v) {
        return (int) (v * c.getResources().getDisplayMetrics().density + 0.5f);
    }

    private static int[] screen(Activity a) {
        DisplayMetrics dm = new DisplayMetrics();
        try {
            a.getWindowManager().getDefaultDisplay().getMetrics(dm);
        } catch (Throwable t) {
            dm.widthPixels = 1080;
            dm.heightPixels = 1920;
        }
        return new int[]{dm.widthPixels, dm.heightPixels};
    }

    private static int clamp(int v, int lo, int hi) {
        if (hi < lo) hi = lo;
        return v < lo ? lo : (v > hi ? hi : v);
    }

    private static void log(String m) {
        System.out.println(TAG + ": " + m);
        android.util.Log.i(TAG, m);
    }
}
