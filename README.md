# 七猫免费小说 7.80 · 导出插件工程（qi-mao-book-export）

在已重打包的破解版 APK 基础上，**静态注入**一个导出插件（无 Xposed / 无 Pine / 无 native hook），直接借用 App 自身的解密器（`com.km.encryption.api.Security`）把缓存密文还原为可阅读的明文 txt，支持分章勾选、整理全集。

> 📖 完整图文介绍见 **[index.html](index.html)**（也可在仓库开启 GitHub Pages 后直接访问）。

## 核心能力
- 悬浮球面板：导出章节（可勾选 / 全选）、整理全集、打开缓存目录、修复密文。
- 分章勾选导出：像原版「全本下载」一样选书 → 勾章节 → 解密导出。
- 实测一本书 **3690 章 10 秒内全部导出，0 失败**；`全集/213697_3690章.txt` = 10,525,358 字纯文本。

## 仓库结构
| 目录 | 内容 |
|---|---|
| `导出插件使用说明.md` / `逆向分析报告.md` | 插件使用文档 / 破解版架构与 VIP 链路分析 |
| `payload/` | 导出插件与 VIP Hook 的源码、frida 脚本 |
| `tools/` | 自写 DEX / AXML / ELF 分析脚本 |
| `build/` | 构建脚本（`make_plugin.py`、`patch_smali.py` 等）+ 插件 Java 源码 |
| `analysis/` | 逆向分析产物（文本） |
| `我的小说/` `我的小说_v2/` `QimaoBooks_raw/` `QimaoBooks_v2/` | 导出小说样例 |
| `out/` | 导出样例与清理报告 |

## 重建导出插件
```bash
python build/make_plugin.py
# 输出 out/七猫免费小说_7.80_导出插件v3.apk（已签名，直接安装）
```

## 说明
为保持仓库轻量，`*.apk / *.zip / *.jar / *.dex` 等二进制与 `build/decoded` 全量 smali 反编译产物已通过 `.gitignore` 排除；需要时可按文档本地重建。

## 相关文档
- [导出插件使用说明.md](导出插件使用说明.md)
- [逆向分析报告.md](逆向分析报告.md)
- [index.html](index.html)
