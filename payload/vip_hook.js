/**
 * 七猫免费小说 (com.kmxs.reader) — VIP 时长 / 会员状态 修改
 *
 * 用法:
 *   frida -U -f com.kmxs.reader -l vip_hook.js --no-pause
 *   或  frida -U -p <pid> -l vip_hook.js
 *
 * 改这两个常量即可控制效果:
 *   VIP_STATUS  会员状态标记, "1" = 会员
 *   VIP_EXPIRE  到期时间(vet 字段)
 */

'use strict';

// ============ 可调参数 ============
var VIP_STATUS = "1";
var VIP_EXPIRE = "2099-12-31 23:59:59";   // 日期串格式
var VIP_EXPIRE_TS = 4102444800;           // 对应 2099-12-31 23:59:59 的秒级时间戳
// =================================

var CLS_RESP = "com.qimao.qmuser.model.response.UserVipInfoResponse";
var CLS_MODEL = "com.qimao.qmuser.model.UserVipModel";
var CLS_CACHE = "ol6";                     // 本地缓存混淆类 (classes3.dex)

function log(m) { console.log("[VIP] " + m); }

function safe(fn, tag) {
    try { fn(); } catch (e) { log("[" + tag + "] " + e); }
}

Java.perform(function () {

    // ---------- 1. 响应实体: 改状态与到期时间 ----------
    safe(function () {
        var R = Java.use(CLS_RESP);

        R.isVipStatus.implementation = function () {
            return true;
        };

        R.getStatus.implementation = function () {
            return VIP_STATUS;
        };

        R.getVipExpiration.implementation = function () {
            // 顺手把字段本身也改掉, 防止别处直接读 vet
            try { this.vet.value = VIP_EXPIRE; } catch (e) {}
            return VIP_EXPIRE;
        };

        log("hooked " + CLS_RESP + " (isVipStatus/getStatus/getVipExpiration)");
    }, "resp");

    // ---------- 2. 解码出口: 解密后立刻改对象字段 ----------
    // 这是最彻底的改法: 服务器返回 -> 解密 -> 反序列化 -> 这里把字段改掉
    // 对应破解版的 setObjectField(Object, String, Object)
    safe(function () {
        var M = Java.use(CLS_MODEL);

        M.decodeVipResponse.implementation = function (resp) {
            var info = this.decodeVipResponse(resp);
            if (info != null) {
                try {
                    var cls = info.getClass();
                    var fStatus = cls.getDeclaredField("status");
                    var fVet = cls.getDeclaredField("vet");
                    fStatus.setAccessible(true);
                    fVet.setAccessible(true);
                    fStatus.set(info, VIP_STATUS);
                    fVet.set(info, VIP_EXPIRE);
                    log("decodeVipResponse -> status=" + VIP_STATUS + " vet=" + VIP_EXPIRE);
                } catch (e) {
                    log("decodeVipResponse field set failed: " + e);
                }
            }
            return info;
        };

        // 保存时也兜一层
        M.saveVipInfo.overload(CLS_RESP).implementation = function (info) {
            if (info != null) {
                try {
                    var cls = info.getClass();
                    var fStatus = cls.getDeclaredField("status");
                    var fVet = cls.getDeclaredField("vet");
                    fStatus.setAccessible(true);
                    fVet.setAccessible(true);
                    fStatus.set(info, VIP_STATUS);
                    fVet.set(info, VIP_EXPIRE);
                } catch (e) {}
            }
            return this.saveVipInfo(info);
        };

        log("hooked " + CLS_MODEL + " (decodeVipResponse/saveVipInfo)");
    }, "model");

    // ---------- 3. 本地缓存: USER_IS_VIP ----------
    // Lol6->Y(Context) 读, Lol6->n1(Context,String) 写
    safe(function () {
        var Cache = Java.use(CLS_CACHE);
        // Lol6->Y(Context) : String  读 USER_IS_VIP, 原默认返回 "0"
        Cache.Y.overload("android.content.Context").implementation = function (ctx) {
            var v = this.Y(ctx);
            return (v === null || v === "0" || v === "") ? VIP_STATUS : v;
        };
        log("hooked cache getter L" + CLS_CACHE + "->Y(Context) -> force " + VIP_STATUS);
    }, "cache");

    // ---------- 4. 可选: 顺手去广告 ----------
    // 破解版有专门的 Set<String> val$adIds 做这个, 这里给个通用兜底
    // 需要时把下面注释打开
    /*
    safe(function () {
        var AdView = Java.use("com.bytedance.sdk.openadsdk.TTAdManagerImpl");
        // ...按实际 SDK 调整
    }, "ad");
    */

    log("done. 进入「我的」页面刷新即可看到会员状态与到期时间");
});
