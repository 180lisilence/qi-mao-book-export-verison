/**
 * 七猫免费小说 (com.kmxs.reader) — 章节正文导出插件 (Frida 版)
 *
 * 把 App 拉取到的章节正文实时落盘到:
 *     <OUT_ROOT>/<书名>/<0001>_<章节名>.txt
 *
 * 同时可选:
 *   MERGE_ONE_FILE = true  -> 额外生成 <OUT_ROOT>/<书名>/<书名>.txt 合并稿
 *   WRITE_INDEX    = true  -> 生成 <OUT_ROOT>/<书名>/index.json 章节清单
 *
 * 用法:
 *   frida -U -f com.kmxs.reader -l book_export.js --no-pause
 * (推荐 -f 冷启动注入, 保证所有拉取都被捕获)
 *
 * 想改导出目录就改下面 OUT_ROOT 一个地方。
 */

'use strict';

// ==================== 可调参数 ====================
var OUT_ROOT = "/sdcard/Download/QimaoBooks";  // 导出根目录
var MERGE_ONE_FILE = true;                     // 每本书额外生成合并 txt
var WRITE_INDEX = true;                        // 生成 index.json
var OVERWRITE = false;                         // true = 已存在也会重写; false = 跳过已有章节
var PAD_NUM = 4;                               // 章节序号补零位数
// ==================================================

var CLS_CHAPTER_ENTITY = "com.qimao.qmreader.reader.model.entity.ChapterContentEntity";
var CLS_PRELOAD_ENTITY = "com.qimao.qmreader.reader.model.entity.PreloadChapterContentEntity";
var CLS_KMCHAPTER = "com.qimao.qmreader.bookinfo.entity.KMChapter";
var CLS_KMBOOK = "com.qimao.qmservice.reader.entity.KMBook";

// chapterId -> { bookId, name, sort }
var metaMap = {};
// bookId -> bookName
var bookMap = {};
// 已写过/正在写的章节, 防止重复 IO
var written = {};
// 每本书已追加到合并稿的章节
var merged = {};

function log(m) { console.log("[EXPORT] " + m); }

function safe(fn, tag) {
    try { fn(); } catch (e) { log("[" + tag + "] " + e); }
}

/** 把任意 Java 对象当作 String 返回 */
function jstr(v) {
    if (v === null || v === undefined) return null;
    try { return String(Java.cast(v, Java.use("java.lang.String"))); }
    catch (e) { try { return String(v); } catch (e2) { return null; } }
}

/** 反射调用无参方法, 拿不到就返回 null —— 兼容版本差异 */
function invoke0(obj, methodName) {
    try {
        var m = obj.getClass().getDeclaredMethod(methodName, null);
        m.setAccessible(true);
        return m.invoke(obj, null);
    } catch (e) { return null; }
}

/** 反射读取字段(含父类字段) */
function readField(obj, fieldName) {
    try {
        var cls = obj.getClass();
        while (cls !== null) {
            try {
                var f = cls.getDeclaredField(fieldName);
                f.setAccessible(true);
                return f.get(obj);
            } catch (e) { }
            cls = cls.getSuperclass();
        }
    } catch (e) { }
    return null;
}

/** 紧凑地从对象里取一个字符串: 优先 getter, 其次字段 */
function grabStr(obj, prop) {
    var getter = "get" + prop.charAt(0).toUpperCase() + prop.slice(1);
    var v = jstr(invoke0(obj, getter));
    if (v !== null && v !== undefined && v !== "") return v;
    return jstr(readField(obj, prop));
}

/** 文件名净化 */
function sanitize(s) {
    if (!s) return "untitled";
    return s.replace(/[\\/:*?"<>|\r\n\t]/g, "_").replace(/\s+/g, " ").trim().substring(0, 120);
}

function pad(n) {
    var s = String(n);
    while (s.length < PAD_NUM) s = "0" + s;
    return s;
}

/* ---------------- Java IO 封装 (Frida JS 没有文件 API) ---------------- */

var _File = null, _FOS = null, _FileWriter = null, _BufferedWriter = null, _OutputStreamWriter = null;

function ensureIO() {
    if (_File) return;
    _File = Java.use("java.io.File");
    _FOS = Java.use("java.io.FileOutputStream");
    _OutputStreamWriter = Java.use("java.io.OutputStreamWriter");
    _BufferedWriter = Java.use("java.io.BufferedWriter");
}

/** 写 UTF-8 文本文件, append=true 时追加 */
function writeText(pathStr, text, append) {
    ensureIO();
    try {
        var f = _File.$new(pathStr);
        var parent = f.getParentFile();
        if (parent !== null && !parent.exists()) parent.mkdirs();

        var fos = _FOS.$new(pathStr, append === true);
        var osw = _OutputStreamWriter.$new(fos, "UTF-8");
        var bw = _BufferedWriter.$new(osw);
        try {
            bw.write(text);
            bw.flush();
        } finally {
            try { bw.close(); } catch (e) { }
        }
        return true;
    } catch (e) {
        log("writeText 失败 " + pathStr + " : " + e);
        return false;
    }
}

function fileExists(pathStr) {
    ensureIO();
    try { return _File.$new(pathStr).exists(); } catch (e) { return false; }
}

/* ---------------- 核心: 落盘 ---------------- */

function resolveBookDir(bookId, fallbackName) {
    var name = sanitize(bookMap[bookId] || fallbackName || ("book_" + bookId));
    if (!bookMap[bookId] && fallbackName) bookMap[bookId] = name;
    return OUT_ROOT + "/" + name;
}

/**
 * @param chapterId 章节 id
 * @param content   正文
 * @param titleHint 预加载场景下给的章节标题
 */
function saveChapter(chapterId, content, titleHint) {
    if (!content) return;
    content = String(content);
    if (content.length < 2) return;

    if (written[chapterId]) return;
    written[chapterId] = true;

    var meta = metaMap[chapterId] || {};
    var bookId = meta.bookId || "unknown";
    var bookDir = OUT_ROOT + "/" + sanitize(bookMap[bookId] || (meta.bookName || ("book_" + bookId)));
    var sort = meta.sort;
    if (sort === undefined || sort === null) sort = 99999;

    var chapName = sanitize(meta.name || titleHint || ("chapter_" + chapterId));
    var fname = (sort === 99999 ? "9999" : pad(sort)) + "_" + chapName + ".txt";
    var path = bookDir + "/" + fname;

    if (!OVERWRITE && fileExists(path)) return;

    var body = content
        .replace(/\r\n/g, "\n")
        .replace(/<br\s*\/?>/gi, "\n")
        .replace(/<\/p>/gi, "\n\n")
        .replace(/<[^>]+>/g, "")
        .replace(/&nbsp;/gi, " ")
        .replace(/&amp;/gi, "&")
        .replace(/&lt;/gi, "<")
        .replace(/&gt;/gi, ">")
        .replace(/&quot;/gi, "\"")
        .replace(/\n{3,}/g, "\n\n")
        .trim();

    var header = chapName + "\n\n";
    if (writeText(path, header + body + "\n")) {
        log("OK  " + path + "  (" + body.length + " 字)");
    }

    if (MERGE_ONE_FILE) {
        var key = bookId + "|" + path;
        if (!merged[key]) {
            merged[key] = true;
            var mergePath = bookDir + "/" + sanitize(bookMap[bookId] || ("book_" + bookId)) + ".txt";
            writeText(mergePath, "\n\n\n" + header + body + "\n", true);
            log("MERGED -> " + mergePath);
        }
    }
}

Java.perform(function () {

    log("导出根目录: " + OUT_ROOT);
    ensureIO();
    try { _File.$new(OUT_ROOT).mkdirs(); } catch (e) { }

    // ---------- 1. 书籍信息: bookId -> bookName ----------
    safe(function () {
        var KMBook = Java.use(CLS_KMBOOK);
        var hookers = ["getBookId", "getBookName"];
        KMBook.getBookId.implementation = function () {
            var id = jstr(this.getBookId());
            if (id) {
                var nm = null;
                try { nm = jstr(this.getBookName()); } catch (e) { }
                if (nm && !bookMap[id]) {
                    bookMap[id] = sanitize(nm);
                    log("识别书籍: " + id + " -> " + nm);
                }
            }
            return id;
        };
    }, "KMBook");

    // ---------- 2. 章节元数据: chapterId -> {bookId,name,sort} ----------
    safe(function () {
        var Ch = Java.use(CLS_KMCHAPTER);
        Ch.getChapterId.implementation = function () {
            var cid = jstr(this.getChapterId());
            if (cid) {
                try {
                    metaMap[cid] = {
                        bookId: jstr(this.getBookId()),
                        name: jstr(this.getChapterName()),
                        sort: this.getChapterSort()
                    };
                } catch (e) { }
            }
            return cid;
        };
    }, "KMChapter");

    // ---------- 3. 正文章节实体 (单章) ----------
    safe(function () {
        var E = Java.use(CLS_CHAPTER_ENTITY);
        E.getContent.implementation = function () {
            var content = jstr(this.getContent());
            if (content) {
                var cid = null;
                try { cid = jstr(this.getId()); } catch (e) { }
                try { cid = cid || jstr(readField(this, "id")); } catch (e) { }
                saveChapter(cid || ("anon_" + Date.now()), content, null);
            }
            return content;
        };
        log("hook 正文实体: " + CLS_CHAPTER_ENTITY);
    }, "ChapterContentEntity");

    // ---------- 4. 预加载实体 (批量), 一次拿多章 ----------
    safe(function () {
        var P = Java.use(CLS_PRELOAD_ENTITY);
        P.getId.implementation = function () {
            var id = jstr(this.getId());

            // 标题在这里一般是书名
            try {
                var title = jstr(this.getTitle());
                if (title) {
                    for (var k in metaMap) {
                        if (metaMap[k].bookId === id && !metaMap[k].bookName) {
                            metaMap[k].bookName = title;
                        }
                    }
                    if (!bookMap[id]) bookMap[id] = sanitize(title);
                }
            } catch (e) { }

            // 批量正文列表
            try {
                var list = this.getChapter_contents();
                if (list !== null && list !== undefined) {
                    var size = list.size();
                    if (size > 0) log("预加载批量正文 " + size + " 章");
                    for (var i = 0; i < size; i++) {
                        try {
                            var item = list.get(i);
                            var content = grabStr(item, "content");
                            var cid = grabStr(item, "id") || grabStr(item, "chapter_id") || grabStr(item, "chapterId");
                            var cname = grabStr(item, "title") || grabStr(item, "chapter_name") || grabStr(item, "chapterName");
                            if (content) {
                                if (cid && !metaMap[cid]) metaMap[cid] = { bookId: id, name: cname, sort: i + 1 };
                                saveChapter(cid || (id + "_" + i), content, cname);
                            }
                        } catch (e2) { }
                    }
                }
            } catch (e3) { }

            return id;
        };
        log("hook 预加载实体: " + CLS_PRELOAD_ENTITY);
    }, "PreloadChapterContentEntity");

    // ---------- 5. 定时写 index.json 章节清单 ----------
    var INDEX_PATH = OUT_ROOT + "/_index.json";
    var chaptersSeen = {};

    setInterval(function () {
        if (!WRITE_INDEX) return;
        Java.perform(function () {
            try {
                var arr = [];
                for (var cid in metaMap) {
                    if (!metaMap.hasOwnProperty(cid)) continue;
                    var m = metaMap[cid];
                    arr.push({
                        chapter_id: cid,
                        book_id: m.bookId || null,
                        book_name: bookMap[m.bookId] || null,
                        chapter_name: m.name || null,
                        sort: m.sort === undefined ? null : m.sort
                    });
                }
                if (arr.length === 0) return;
                if (arr.length === chaptersSeen.count) return;
                chaptersSeen.count = arr.length;
                arr.sort(function (a, b) {
                    return (a.sort || 0) - (b.sort || 0);
                });
                writeText(INDEX_PATH, JSON.stringify(arr, null, 2), false);
            } catch (e) { }
        });
    }, 3000);

    log("注入完成。现在去 App 里打开书 / 用离线下载拉章节, 文本文件会实时出现在 " + OUT_ROOT);
});
