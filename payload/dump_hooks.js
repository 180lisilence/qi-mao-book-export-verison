/**
 * 把破解版内置的 37+ 个 hook 目标全部打出来
 *
 * 原理: 破解版的 hook 逻辑在 libProtect2C.so 里且字符串加密, 静态读不到。
 *      但它最终必须通过 Pine / XposedBridge 注册 hook, 在注册入口上挂钩子
 *      就能拿到全部目标方法。
 *
 * 用法:
 *   frida -U -f com.kmxs.reader -l dump_hooks.js --no-pause
 *   然后正常用一会儿 App (进书城/阅读页/我的), 观察输出
 *
 * 注意: 要在 App 启动早期注入 (-f  spawn 模式), 否则注册已完成会漏
 */

'use strict';

function log(m) { console.log("[DUMP] " + m); }

function desc(m) {
    try {
        return m.getDeclaringClass().getName() + "->" + m.getName() + "()";
    } catch (e) {
        return String(m);
    }
}

Java.perform(function () {

    // ---------- 1. Xposed 层 ----------
    try {
        var XB = Java.use("de.robv.android.xposed.XposedBridge");
        XB.hookMethod.overload("java.lang.reflect.Member",
                               "de.robv.android.xposed.XC_MethodHook")
            .implementation = function (member, callback) {
                log("XposedBridge.hookMethod: " + desc(member)
                    + "  cb=" + callback.getClass().getName());
                return this.hookMethod(member, callback);
            };
        log(" hooked XposedBridge.hookMethod");
    } catch (e) { log("XposedBridge: " + e); }

    try {
        var XH = Java.use("de.robv.android.xposed.XposedHelpers");
        var fahm = XH.findAndHookMethod.overloads;
        for (var i = 0; i < fahm.length; i++) {
            (function (ov) {
                ov.implementation = function () {
                    var args = [].slice.call(arguments);
                    // 最后一个参数是 callback
                    var cb = args[args.length - 1];
                    var cls = args[0];
                    var mname = (typeof args[1] === "string") ? args[1] : null;
                    log("findAndHookMethod: class=" + cls + " method=" + mname
                        + " cb=" + (cb && cb.getClass ? cb.getClass().getName() : cb));
                    return ov.apply(this, arguments);
                };
            })(fahm[i]);
        }
        log(" hooked XposedHelpers.findAndHookMethod (" + fahm.length + " overloads)");
    } catch (e) { log("XposedHelpers: " + e); }

    // ---------- 2. Pine 层 (ART 方法 hook 引擎) ----------
    try {
        var Pine = Java.use("top.canyie.pine.Pine");
        var hs = Pine.hook.overloads;
        for (var j = 0; j < hs.length; j++) {
            (function (ov) {
                ov.implementation = function () {
                    var args = [].slice.call(arguments);
                    // Pine.hook(Member, MethodHook)  或  Pine.hook(Class, String, ...)
                    var t = args[0];
                    log("Pine.hook: target=" + (t && t.getName ? desc(t) : t)
                        + "  args=" + args.length);
                    return ov.apply(this, arguments);
                };
            })(hs[j]);
        }
        log(" hooked Pine.hook (" + hs.length + " overloads)");
    } catch (e) { log("Pine: " + e); }

    // ---------- 3. 破解者自己的回调类实例化 ----------
    // 七猫免费小说.Ho*/H* 都是 XC_MethodHook 子类, 抓它们的构造能数出 hook 数量
    try {
        var XC = Java.use("de.robv.android.xposed.XC_MethodHook");
        var hookedClasses = {};
        var origInit = XC.$init;
        // Xposed 回调是被动调用的, 这里改为轮询统计已加载的回调类
        var timer = setInterval(function () {
            Java.perform(function () {
                try {
                    var cl = Java.use("java.lang.ClassLoader");
                    // 枚举已加载类中包名含 "七猫" 的
                    var appCls = Java.use("android.app.Application");
                    // 通过 XposedBridge 的 hook 记录拿更准, 这里只做兜底输出
                } catch (e) {}
            });
        }, 10000);
        log(" callback-class watcher started");
    } catch (e) { log("XC_MethodHook: " + e); }

    // ---------- 4. 直接抓 native 注册入口 ----------
    // Protect2C 的 Hidden0.special_clinit_* 是每个 hook 类的 native 注册入口
    try {
        var H0 = Java.use("Protect2C.hidden.Hidden0");
        var ms = H0.class.getDeclaredMethods();
        for (var k = 0; k < ms.length; k++) {
            var name = ms[k].getName();
            if (name.indexOf("special_clinit") === 0) {
                (function (n) {
                    try {
                        H0[n].overload("java.lang.Class").implementation = function (c) {
                            log("special_clinit " + n + " -> " + (c ? c.getName() : c));
                            return H0[n].call(this, c);
                        };
                    } catch (e) {}
                })(name);
            }
        }
        log(" hooked Protect2C.hidden.Hidden0.special_clinit_* (" + ms.length + " methods)");
    } catch (e) { log("Hidden0: " + e); }

    // ---------- 5. 抓 setObjectField (破解者改字段的手法) ----------
    try {
        var Main = Java.use("七猫免费小说".replace("七猫免费小说", "七猫免费小说"));
        log(" found main class");
    } catch (e) {
        // 类名带 \0, Java.use 直接写不出来, 改用反射
        try {
            var Class = Java.use("java.lang.Class");
            var Thread = Java.use("java.lang.Thread");
            var ctx = Thread.currentThread().getContextClassLoader();
            try {
                var c = Class.forName("七猫免费小说", true, ctx);
                log(" found main class via reflection: " + c);
            } catch (e2) {
                log(" main class not loaded yet: " + e2);
            }
        } catch (e3) {}
    }

    log("dump 已就绪, 操作 App 观察输出 (建议: 我的 -> 会员中心 -> 阅读页)");
});
