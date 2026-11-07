# -*- coding: utf-8 -*-
"""在 apktool 反编译出的 smali 上做静态注入 (不依赖任何 hook 框架)。"""
import io, os, sys

DEC = "build/decoded"


def patch(path, old, new, tag):
    p = os.path.join(DEC, path)
    if not os.path.exists(p):
        print("  [!] 不存在:", path)
        return False
    s = io.open(p, encoding="utf-8").read()
    if "kmxs/export" in s and tag in s:
        print("  [=] 已注入过:", tag)
        return True
    if old not in s:
        print("  [!] 未匹配到目标方法:", tag)
        return False
    s = s.replace(old, new, 1)
    io.open(p, "w", encoding="utf-8").write(s)
    print("  [+] 注入成功:", tag)
    return True


# ---------- 1. ChapterContentEntity.getContent() -> Boot.dumpRaw(id, content) ----------
CE = "smali_classes3/com/qimao/qmreader/reader/model/entity/ChapterContentEntity.smali"
CE_OLD = """.method public getContent()Ljava/lang/String;
    .locals 1

    iget-object v0, p0, Lcom/qimao/qmreader/reader/model/entity/ChapterContentEntity;->content:Ljava/lang/String;

    return-object v0
.end method"""
CE_NEW = """.method public getContent()Ljava/lang/String;
    .locals 2

    iget-object v0, p0, Lcom/qimao/qmreader/reader/model/entity/ChapterContentEntity;->content:Ljava/lang/String;

    # >>> DUMP_PLUGIN >>>
    :try_start_dump
    iget-object v1, p0, Lcom/qimao/qmreader/reader/model/entity/ChapterContentEntity;->id:Ljava/lang/String;

    invoke-static {v1, v0}, Lcom/kmxs/export/Boot;->dumpRaw(Ljava/lang/String;Ljava/lang/String;)V
    :try_end_dump
    .catch Ljava/lang/Throwable; {:try_start_dump .. :try_end_dump} :catch_dump
    # <<< DUMP_PLUGIN <<<

    return-object v0

    :catch_dump
    move-exception v1

    return-object v0
.end method"""

# ---------- 2. KMChapter.getChapterName() -> Boot.noteMeta(id, bookId, name, sort) ----------
KM = "smali_classes3/com/qimao/qmreader/bookinfo/entity/KMChapter.smali"
KM_OLD = """.method public getChapterName()Ljava/lang/String;
    .locals 1

    iget-object v0, p0, Lcom/qimao/qmreader/bookinfo/entity/KMChapter;->chapterName:Ljava/lang/String;

    return-object v0
.end method"""
KM_NEW = """.method public getChapterName()Ljava/lang/String;
    .locals 4

    iget-object v0, p0, Lcom/qimao/qmreader/bookinfo/entity/KMChapter;->chapterName:Ljava/lang/String;

    # >>> DUMP_PLUGIN >>>
    :try_start_meta
    iget-object v1, p0, Lcom/qimao/qmreader/bookinfo/entity/KMChapter;->chapterId:Ljava/lang/String;

    iget-object v2, p0, Lcom/qimao/qmreader/bookinfo/entity/KMChapter;->bookId:Ljava/lang/String;

    iget v3, p0, Lcom/qimao/qmreader/bookinfo/entity/KMChapter;->chapterSort:I

    invoke-static {v3}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v3

    invoke-static {v1, v2, v0, v3}, Lcom/kmxs/export/Boot;->noteMeta(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V
    :try_end_meta
    .catch Ljava/lang/Throwable; {:try_start_meta .. :try_end_meta} :catch_meta
    # <<< DUMP_PLUGIN <<<

    return-object v0

    :catch_meta
    move-exception v1

    return-object v0
.end method"""

print("== smali 静态注入 ==")
ok1 = patch(CE, CE_OLD, CE_NEW, "ChapterContentEntity.getContent")
ok2 = patch(KM, KM_OLD, KM_NEW, "KMChapter.getChapterName")
print("完成:", ok1 and ok2)
