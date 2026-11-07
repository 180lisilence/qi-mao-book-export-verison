# 方案 C：smali 硬改（不引入 hook 框架，规避所有反 hook 检测）

改的是业务代码本身，不会留下 Xposed/Frida/Pine 特征，最稳。

## 前置

```bash
apktool d 七猫免费小说_7.80.apk -o qimao_src
# 若 apktool 因 18 个 dex 报错，加 --only-main-classes
```

目标文件（均在 `qimao_src/smali_classes6/`，dex 编号可能因 apktool 略有出入，按路径找）：

```
smali_classes6/com/qimao/qmuser/model/response/UserVipInfoResponse.smali
smali_classes6/com/qimao/qmuser/model/UserVipModel.smali
smali_classes3/ol6.smali
```

---

## 1. UserVipInfoResponse.smali —— 会员状态 + 到期时间

### 1.1 `isVipStatus()` 改为恒返回 true

原方法（Robust 插桩版）结尾是：

```smali
.method public isVipStatus()Z
    .locals 1
    # ... Robust PatchProxy 检查 ...
    const-string v0, "1"
    iget-object v1, p0, Lcom/qimao/qmuser/model/response/UserVipInfoResponse;->status:Ljava/lang/String;
    invoke-virtual {v0, v1}, ...equals...
    move-result v0
    return v0
.end method
```

**替换为**：

```smali
.method public isVipStatus()Z
    .locals 1

    const/4 v0, 0x1

    return v0
.end method
```

### 1.2 `getVipExpiration()` 改为返回固定远期时间

原方法：

```smali
.method public getVipExpiration()Ljava/lang/String;
    .locals 1
    iget-object v0, p0, Lcom/qimao/qmuser/model/response/UserVipInfoResponse;->vet:Ljava/lang/String;
    return-object v0
.end method
```

**替换为**：

```smali
.method public getVipExpiration()Ljava/lang/String;
    .locals 1

    const-string v0, "2099-12-31 23:59:59"

    return-object v0
.end method
```

### 1.3 顺带把 `status` 字段默认值改掉（可选，更彻底）

在这个类的 `<init>()V` 里，`.locals` 之后加：

```smali
    const-string v0, "1"
    iput-object v0, p0, Lcom/qimao/qmuser/model/response/UserVipInfoResponse;->status:Ljava/lang/String;

    const-string v0, "2099-12-31 23:59:59"
    iput-object v0, p0, Lcom/qimao/qmuser/model/response/UserVipInfoResponse;->vet:Ljava/lang/String;
```

> 若 `<init>` 的 `.locals 0`，记得改成 `.locals 1`。

---

## 2. UserVipModel.smali —— 解码出口（可选，最彻底）

`decodeVipResponse(UserVipResponse)` 返回 `UserVipInfoResponse`，在 `return-object vX` 之前插入改字段代码：

```smali
    # --- 注入开始 ---
    move-object-object vT, vX          # vX = 返回值寄存器
    if-eqz vT, :skip_patch

    const-string vS, "1"
    iput-object vS, vT, Lcom/qimao/qmuser/model/response/UserVipInfoResponse;->status:Ljava/lang/String;

    const-string vS, "2099-12-31 23:59:59"
    iput-object vS, vT, Lcom/qimao/qmuser/model/response/UserVipInfoResponse;->vet:Ljava/lang/String;

    :skip_patch
    # --- 注入结束 ---
```

> 寄存器名按实际 smali 调整；若 `.locals` 不够，往上加。

`saveVipInfo(UserVipInfoResponse)` 同理，改完后服务器下次刷新会覆盖 —— 所以**必须同时改 `decodeVipResponse`**。

---

## 3. ol6.smali —— 本地缓存 USER_IS_VIP

`Y(Landroid/content/Context;)Ljava/lang/String;` 里读 `USER_IS_VIP` 的默认值是 `"0"`：

```smali
    const-string v0, "USER_IS_VIP"
    const-string v1, "0"          # <-- 改这里
```

把 `"0"` 改成 `"1"`：

```smali
    const-string v0, "USER_IS_VIP"
    const-string v1, "1"
```

`d(Landroid/content/Context;)V`（登出清缓存）里也有一处：

```smali
    const-string v0, "USER_IS_VIP"
    const-string v2, "0"          # <-- 同样改成 "1"，避免登出后被清回非会员
```

---

## 4. 重新打包与签名

```bash
apktool b qimao_src -o qimao_patched.apk

keytool -genkey -v -keystore qimao.keystore -alias qimao \
        -keyalg RSA -keysize 2048 -validity 10000 -storepass 123456

apksigner sign --ks qimao.keystore --ks-key-alias qimao \
               --ks-pass pass:123456 --key-pass pass:123456 \
               --out qimao_signed.apk qimao_patched.apk

apksigner verify qimao_signed.apk
adb install -r qimao_signed.apk
```

---

## 5. 注意事项

1. **dex 编号**：apktool 会把 `classes6.dex` 解到 `smali_classes6/`，但某些版本会合并/重排。找不到文件就 `grep -r "UserVipInfoResponse" qimao_src/smali*/`。
2. **Robust 插桩**：这些方法开头都有 `PatchProxyResult`/`changeQuickRedirect` 检查。官方可能下发热修复补丁覆盖你的改动 —— 若要防止，可把 `changeQuickRedirect` 的 `sget-object` 改成 `const/4 vX, 0x0`（禁用热修代理）。
3. **Odex/基线**：`assets/dexopt/baseline.prof` 存在，不影响功能。
4. **别动 classes18.dex 和 classes17.dex**：那是破解者的东西。想做干净包就把这两个 dex 和 `libProtect2C.so`、`libpinesafecheck.so` 一起删掉（删了之后 APK 就是官方原包 + 你自己的 patch）。
